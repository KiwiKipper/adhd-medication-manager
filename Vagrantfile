# -*- mode: ruby -*-
# vi: set ft=ruby :

# Host-only networking must stay inside 192.168.56.0/21 -- VirtualBox refuses
# other ranges by default.
# NODES = {
#   "web" => "192.168.56.10",
#   "pk"  => "192.168.56.11",
#   "db"  => "192.168.56.12",
# }

# Vagrant.configure("2") do |config|
#   config.vm.box = "bento/ubuntu-22.04"

#   NODES.each do |name, ip|
#     config.vm.define name do |node|
#       node.vm.hostname = name
#       node.vm.network "private_network", ip: ip

#       node.vm.provider "virtualbox" do |vb|
#         vb.name = name
#         vb.memory = 1024
#         vb.cpus = 1
#       end
#     end
#   end
# end



Vagrant.configure("2") do |config|

  servers=[
    {
      :hostname => "db",
      :box => "bento/ubuntu-18.04",
      :ip => "192.168.56.10",
      :ssh_port => 2200

    },
    {
      :hostname => "pk",
      :box => "bento/ubuntu-18.04",
      :ip => "192.168.56.11",
      :ssh_port => 2201

    },
    {
      :hostname => "web",
      :box => "bento/ubuntu-18.04",
      :ip => "192.168.56.12",
      :ssh_port => 2202

    },
  ]

  servers.each do |machine|
    config.vm.define machine[:hostname] do |node|
      node.vm.box = machine[:box]
      node.vm.hostname = machine[:hostname]
      node.vm.network :private_network, ip: machine[:ip]
      node.vm.network "forwarded_port", guest: 22, host: machine[:ssh_port], id: "ssh"
      node.vm.provision "shell", path: "provision/#{machine[:hostname]}.sh"

      node.vm.provider :virtualbox do |vb|
        vb.customize ["modifyvm", :id, "--memory", 1024]
        vb.customize ["modifyvm", :id, "--cpus", 1]
      end
    end
  end

end
# vagrant validate
# if succesfull continue
# vagrant up