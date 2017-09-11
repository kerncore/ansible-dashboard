#!/usr/bin/env python3

import datetime
import json
import logging
import os
import pytz
import re
import sys
import time

from pprint import pprint
from bs4 import BeautifulSoup
from pymongo import MongoClient
from selenium import webdriver
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
from urlextract import URLExtract
from urllib.error import URLError


class SFDCCrawler(object):

    DATABASE_NAME = 'sfdc'
    COLLECTION_NAME = 'cases'

    def __init__(self, url, username, password):

        self.url = url
        self.username = username
        self.password = password

        self.client = MongoClient()
        self.db = getattr(self.client, self.DATABASE_NAME)
        self.collection = getattr(self.db, self.COLLECTION_NAME)

        capabilities = webdriver.DesiredCapabilities.FIREFOX.copy()
        capabilities['javascriptEnabled'] = True
        capabilities['platform'] = 'WINDOWS'
        capabilities['version'] = '10'

        self.extractor = URLExtract()
        self.driver = webdriver.PhantomJS(desired_capabilities=capabilities, service_log_path='/tmp/phantom.log')
        self.driver.implicitly_wait(20)
        self.driver.set_window_size(1920, 1080)

    def close(self):
        try:
            self.driver.close()
        except Exception as e:
            logging.error(e)

    def login(self):
        ''' Handle Red Hat's SSO login '''
        self.driver.get(self.url)
        time.sleep(2)

        logging.debug('logging into SSO as {}'.format(self.username))
        self.driver.find_element_by_id('username').send_keys(self.username)
        self.driver.find_element_by_id('password').send_keys(self.password)
        self.driver.find_element_by_id('_eventId_submit').click()
        time.sleep(2)

    def search_cases(self, phrase):
        ''' Use the top level search bar to paginate through related cases by phrase '''
        logging.debug('searching for cases by: {}'.format(phrase))
        self.driver.find_element_by_id('phSearchInput').send_keys(phrase)
        self.driver.find_element_by_id('phSearchButton').click()
        time.sleep(2)
        ssummary = self.driver.find_element_by_id('selectedSummary')

        # show cases and ignore the accounts
        cases_a = None
        for div in ssummary.find_elements_by_tag_name('div'):
            if div.get_attribute('data_title') == 'Cases':
                links = div.find_elements_by_tag_name('a')
                for link in links:
                    if link.get_attribute('title').startswith('Cases '):
                        cases_a = link
                        break
                break
        logging.debug('click on the cases view filter')
        cases_a.click()
        time.sleep(5)
        self.driver.save_screenshot('test.png')

        case_numbers = []
        page_count = 0

        while True:

            #self.driver.save_screenshot('page-{}.png'.format(page_count))
            page_count += 1

            logging.info('looking for case body')
            for tr in self.driver.find_element_by_id('Case_body').find_elements_by_tag_name('tr'):
                tr_class = tr.get_attribute('class') or ''
                if not tr_class.strip().startswith('dataRow'):
                    #print(tr_class)
                    continue
                th = tr.find_element_by_tag_name('th')
                number = th.text
                url = th.find_element_by_tag_name('a').get_attribute('href')
                url = url.split('?')[0]
                case_numbers.append((number, url))

            logging.info('find url for next page of cases')
            nextp = self.driver.find_element_by_xpath("//*[text()='Next Page']")
            if not nextp:
                break
            if nextp.get_attribute('class') != 'pShowMore':
                break
            nextp.click()
            time.sleep(4)

        return case_numbers

    def get_and_parse_report(self, report_url):
        logging.info('fetch report {}'.format(report_url))
        self.driver.get(report_url)
        logging.info('sleep 5s while report loads results')
        time.sleep(5)
        try:
            self.driver.find_element_by_class_name('reportOutput')
        except NoSuchElementException:
            import epdb; epdb.st()

        # <div style="display:none;" id="errorTitle">Time limit exceeded</div>

        # <div class="reportOutput">
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        report_output_div = soup.find('div', {'class': 'reportOutput'})
        if not report_output_div:
            return ([], [])

        column_names = []
        column_data = []

        case_number = None
        trs = report_output_div.findAll('tr')
        for idtr,tr in enumerate(trs):

            if idtr == 0:
                for div in tr.findAll('div'):
                    cname = div.text.strip()
                    column_names.append(cname)
                    if cname == 'Case Number':
                        column_names.append('Case URL')
                continue

            tds = tr.findAll('td')
            cdata = []
            for idtd,td in enumerate(tds):
                logging.debug('{} - {}'.format(idtd, td.text))
                cdata.append(td.text.strip())
                if column_names[idtd] == 'Case Number' and idtr > 0:
                    try:
                        href = td.find('a').attrs['href']
                        href = self.url.rstrip('/') + href
                        cdata.append(href)
                    except Exception as e:
                        pass
            if len(cdata) == len(column_names):
                column_data.append(cdata)
            #elif cdata:
            #    import epdb; epdb.st()

        # delete the last row
        column_data = column_data[:-1]

        logging.info('report parsing finished')
        return (column_names, column_data)

    def get_and_parse_case(self, caseurl, number=None):

        logging.info('fetching [{}] {}'.format(number, caseurl))
        self.driver.get(caseurl)
        time.sleep(4)
        #logging.info('screenshot {}'.format(caseurl))
        #self.driver.save_screenshot('case-{}.png'.format(number))

        # use bs4 now because selenium is horribly slow here
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        # <pre class="transcriptStyle privateTranscript">
        try:
            transcript = soup.find('pre', {'class': 'transcriptStyle privateTranscript'}).text
        except:
            transcript = ''

        logging.info('find casesummaryview')
        summary = soup.find(id='caseSummaryView')

        logging.info('find detaillist')
        details = {}
        detail_table = soup.find('table', {'class': 'detailList'})
        if not detail_table:
            # probably a restricted case
            return {}

        logging.info('find detaillist tds')
        tds = detail_table.find_all('td')
        logging.info('{} total tds'.format(len(tds)))

        logging.info('iterate through detail tds')
        key = None
        for idt,td in enumerate(tds):

            logging.debug('get class for td[{}]'.format(idt))
            class_name = td.attrs.get('class', '')
            if isinstance(class_name, list):
                class_name = class_name[0]

            try:
                value = td.find('span').text
                if td.find('script'):
                    stext = td.find('script').text
                    value = value.replace(stext, '')
            except Exception as e:
                #logging.error(e)
                value = td.text

            if value:
                value = value.replace('\n', '')
                value = value.replace('\t', '')
                value = value.strip()

            if class_name == 'labelCol':
                key = value
                key = key.replace(' ', '_')
                key = key.lower()

            elif class_name == 'dataCol' or class_name.startswith('dataCol'):
                if key:
                    details[key] = value
                    if key == 'case_number':
                        details['case_number'] = value.replace(' [View Hierarchy]', '')
                        details['case_url'] = td.find('a').attrs['href']
                    if key.endswith('_by'):
                        #'created_by': 'Foo, Bar (2017-08-24 20:28:20Z)'
                        thiskey = key.rsplit('_', 1)[0]
                        thiskey += '_at'
                        thisval = value.split('(')[1]
                        thisval = thisval.replace(')', '')
                        details[thiskey] = thisval
                        details[key] = value.split('(')[0].strip()

        comments = []
        pagecount = 0
        while True:
            pagecount += 1
            cdivs = soup.select("div[class*=CommentDisplay]")

            for cdiv in cdivs:
                comment = {
                    'user': None,
                    'date': None,
                    'body': None,
                    'private': True,
                }
                classes = [x for x in cdiv.attrs.get('class')]
                if [x for x in classes if 'public' in x]:
                    comment['private'] = False
                author = cdiv.find('div', {'class': 'authorship'})
                try:
                    comment['user'] = author.find('a').text
                except AttributeError:
                    pass
                try:
                    comment['date'] = author.text.replace(comment['user'], '').replace('Created By:', '').strip()
                except TypeError:
                    pass
                body = cdiv.find('pre', {'class': 'caseCommentStyle'})
                if body:
                    try:
                        comment['body'] = body.text
                    except AttributeError:
                        pass
                comments.append(comment)

            # find the link to the next page of comments and click it
            paginator = soup.find('div', {'class': 'backgrid-paginator'})
            lis = paginator.find_all('li')
            nextpages = []
            for li in lis:
                classname = li.attrs.get('class')
                if classname:
                    classname = classname[0]
                if classname and classname == 'disabled':
                    continue
                nextpages.append(li.find('a'))

            nextpages = [x for x in nextpages if x.attrs['title'] == 'Next']
            if not nextpages:
                nexta = self.driver.find_element_by_xpath("//a[@title='Next']")
                break

            logging.info('time to click!')
            nexta = self.driver.find_element_by_xpath("//a[@title='Next']")
            if not nexta:
                break
            try:
                nexta.click()
            except ElementNotVisibleException:
                break
            time.sleep(1)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        links = []
        #for txt in [summary, transcript] + [x['body'] for x in comments]:
        for txt in [soup.text] + [x['body'] for x in comments]:
            # href="https://github.com/ansible/ansible/issues/23340"
            if 'http' in txt:
                links += self.extractor.find_urls(txt)
        links = sorted(set(links))
        links = [x.strip() for x in links if x.strip()]
        links = [x for x in links if x.startswith('http')]

        github_issues = []
        github_urls = [x for x in links if 'github.com' in x and ('issue' in x or 'pull' in x)]
        for gi in github_urls:
            m = re.search('https://github.com/.*/.*/(issues|issue|pulls|pull)/\d+', gi)
            if m:
                github_issues.append(gi[m.start():m.end()])

        cdata = {
            'url': caseurl,
            'details': details,
            'title': soup.title.text,
            'transcript': transcript,
            'summary': summary.text,
            'comments': comments,
            'links': links,
            'github_urls': github_urls,
            'github_issues': github_issues
        }

        return cdata


if __name__ == "__main__":

    root = logging.getLogger()
    #root.setLevel(logging.DEBUG)
    root.setLevel(logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    root.addHandler(ch)

    url = 'https://gss.my.salesforce.com/'
    username = os.environ.get('SFDC_USERNAME')
    password = os.environ.get('SFDC_PASSWORD')

    sfdc = SFDCCrawler(url, username, password)
    sfdc.login()

    # get timestamps
    casemap = {}

    reports = [
        'https://gss.my.salesforce.com/00OA0000006BMZf',
        'https://gss.my.salesforce.com/00OA0000006BMBO',
        'https://gss.my.salesforce.com/00OA0000006BM9c'
    ]

    for report in reports:
        _results = sfdc.get_and_parse_report(report)
        logging.info('{} rows found in report'.format(len(_results[1])))

        number_idx = _results[0].index('Case Number')
        url_idx = _results[0].index('Case URL')
        if 'Last Update Date' in _results[0]:
            timestamp_idx = _results[0].index('Last Update Date')
        else:
            timestamp_idx = _results[0].index('Case Date/Time Last Modified')

        for case in _results[1]:
            url = case[url_idx]
            if url not in casemap:
                casemap[url] = {}
            casemap[url]['number'] = case[number_idx]
            if not case[number_idx].isdigit():
                import epdb; epdb.st()
            casemap[url]['url'] = url
            casemap[url]['updated_at'] = case[timestamp_idx]
            casemap[url]['report'] = report
            casemap[url]['meta'] = {}
            for idc,col in enumerate(case):
                colname = _results[0][idc]
                casemap[url]['meta'][colname] = col
            #import epdb; epdb.st()

    # get+cache or load the case urls
    cases_file = '/tmp/cases.json'
    if not os.path.isfile(cases_file):
        cases = sfdc.search_cases('ansible')
        with open(cases_file, 'w') as f:
            f.write(json.dumps(cases, indent=2))
    else:
        with open(cases_file, 'r') as f:
            cases = json.loads(f.read())

    for case in cases:
        url = case[1].split('?')[0]
        if url not in casemap:
            casemap[url] = {
                'number': case[0],
                'url': url,
                'updated_at': None
            }

    items = casemap.items()
    items = sorted(items, key=lambda x: x[1]['number'])
    total = len(items)

    for itemid,item in enumerate(items):

        logging.info('{}|{}'.format(total, itemid))

        number = item[1]['number']
        url = item[1]['url']
        updated_at = item[1]['updated_at']

        fetch = False
        _cdata = {}
        fn = '/var/sfdc/cases/{}.json'.format(number)
        if not os.path.isfile(fn):
            logging.info('{} has no cached data'.format(number))
            fetch = True
        else:
            with open(fn, 'r') as f:
                _cdata = json.loads(f.read())

        if not fetch and not _cdata.get('details'):
            logging.info('{} has no details'.format(number))
            fetch = True
        if not fetch and not _cdata.get('details', {}).get('last_update_at'):
            logging.info('{} has no last_updated_at'.format(number))
            fetch = True

        if not fetch and updated_at:

            utc = pytz.utc
            eastern = pytz.timezone('US/Eastern')

            # from the report view - 9/24/2016 4:45 AM
            ua = updated_at
            ua = datetime.datetime.strptime(ua, '%m/%d/%Y %H:%M %p')
            ua = utc.localize(ua)

            # inside ticket - 2015-12-03 16:07:19Z
            lu = _cdata['details']['last_update_at']
            lu = datetime.datetime.strptime(lu, '%Y-%m-%d %H:%M:%SZ')
            lu = utc.localize(lu)
            lu = lu.astimezone(eastern)

            if lu.year < ua.year:
                logging.info('{} year is behind'.format(number))
                fetch = True

            if not fetch and lu.month < ua.month:
                logging.info('{} month is behind'.format(number))
                fetch = True

            if not fetch and lu.day < ua.day:
                logging.info('{} day is behind'.format(number))
                fetch = True

        if fetch or not os.path.isfile(fn):
            try:
                cdata = sfdc.get_and_parse_case(url, number=number)
            except (URLError, StaleElementReferenceException):
                sfdc.close()
                sfdc = SFDCCrawler(url, username, password)
                sfdc.login()

            try:
                with open(fn, 'w') as f:
                    f.write(json.dumps(cdata, indent=2, sort_keys=True))
            except Exception as e:
                print(e)

        if os.path.isfile(fn):
            with open(fn, 'r') as f:
                cdata = json.loads(f.read())

            mdata = {
                'url': cdata['url'],
                'product': cdata.get('details', {}).get('product'),
                'status': cdata.get('details', {}).get('status'),
                'severity': cdata.get('details', {}).get('severity'),
                'github_issues': cdata.get('github_issues', []),
            }

            # put it into mongo
            sfdc.collection.replace_one({'rul': mdata['url']}, mdata, True)
            #import epdb; epdb.st()
