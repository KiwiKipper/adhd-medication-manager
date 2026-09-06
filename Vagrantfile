# -*- mode: ruby -*-
# vi: set ft=ruby :

# Host-only networking must stay inside 192.168.56.0/21 -- VirtualBox refuses
# other ranges by default.
NODES = {
  "web" => "192.168.56.10",
  "pk"  => "192.168.56.11",
  "db"  => "192.168.56.12",
}

Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-22.04"

  NODES.each do |name, ip|
    config.vm.define name do |node|
      node.vm.hostname = name
      node.vm.network "private_network", ip: ip

      node.vm.provider "virtualbox" do |vb|
        vb.name = name
        vb.memory = 1024
        vb.cpus = 1
      end
    end
  end
end
