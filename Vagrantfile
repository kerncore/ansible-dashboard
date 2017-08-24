# -*- mode: ruby -*-
# vi: set ft=ruby :

ENV['DEFAULT_VAGRANT_PROVIDER'] = "virtualbox"

Vagrant.configure("2") do |config|
  config.vm.box = "fedora/26-cloud-base"
  config.vm.box_check_update = false

  # nginx
  config.vm.network "forwarded_port", guest: 8000, host: 8000

  # flower
  config.vm.network "forwarded_port", guest: 5555, host: 5555

  config.vm.provider "virtualbox" do |vb|
    vb.cpus = "4"
    vb.memory = "8096"
  end

  config.vm.provision "shell", inline: "dnf clean all; dnf -y update"

  config.vm.provision "ansible_local" do |ansible|
      ansible.playbook = 'site.yml'
  end

end
