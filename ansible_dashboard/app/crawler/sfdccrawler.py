#!/usr/bin/env python3

import logging
import os
import sys
import time


from bs4 import BeautifulSoup
from selenium import webdriver


class SFDCCrawler(object):

    def __init__(self, url, username, password):
        self.url = url
        self.username = username
        self.password = password

        capabilities = webdriver.DesiredCapabilities.FIREFOX.copy()
        capabilities['javascriptEnabled'] = True
        capabilities['platform'] = 'WINDOWS'
        capabilities['version'] = '10'

        self.driver = webdriver.PhantomJS(desired_capabilities=capabilities, service_log_path='/tmp/phantom.log')
        self.driver.implicitly_wait(10)
        self.driver.set_window_size(1920, 1080)

    def login(self):
        ''' Handle Red Hat's SSO login '''
        self.driver.get(self.url)
        time.sleep(2)
        #src = self.driver.page_source
        #soup = BeautifulSoup(src, 'html.parser')

        logging.debug('logging into SSO as {}'.format(self.username))
        self.driver.find_element_by_id('username').send_keys(self.username)
        self.driver.find_element_by_id('password').send_keys(self.password)
        self.driver.find_element_by_id('_eventId_submit').click()
        time.sleep(2)

        #src = self.driver.page_source
        #soup = BeautifulSoup(src, 'html.parser')
        #import epdb; epdb.st()

    def search_cases(self, phrase):
        ''' Use the top level search bar to paginate through related cases by phrase '''
        logging.debug('searching for cases by: {}'.format(phrase))
        self.driver.find_element_by_id('phSearchInput').send_keys(phrase)
        self.driver.find_element_by_id('phSearchButton').click()
        time.sleep(2)
        ssummary = self.driver.find_element_by_id('selectedSummary')

        # show cases and ignore the accounts
        cases = None
        for div in ssummary.find_elements_by_tag_name('div'):
            if div.get_attribute('data_title') == 'Cases':
                cases = div
                break
        logging.debug('click on the cases view filter')
        cases.click()

        print('#############################################################################')

        case_numbers = []
        for tr in self.driver.find_element_by_id('Case_body').find_elements_by_tag_name('tr'):

            tr_class = tr.get_attribute('class') or ''
            if not tr_class.strip().startswith('dataRow'):
                print(tr_class)
                continue

            th = tr.find_element_by_tag_name('th')
            case_numbers.append(th.text)

        import epdb; epdb.st()




if __name__ == "__main__":
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    root.addHandler(ch)

    url='https://gss--c.na7.visual.force.com/'
    username=os.environ.get('SFDC_USERNAME')
    password=os.environ.get('SFDC_PASSWORD')
    #import epdb; epdb.st()

    sfdc = SFDCCrawler(url, username, password)
    #time.sleep(10)
    sfdc.login()
    sfdc.search_cases('ansible')

    import epdb; epdb.st()