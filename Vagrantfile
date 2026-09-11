# -*- mode: ruby -*-
# vi: set ft=ruby :

# Three nodes on a host-only private network, one per tier: db, backend
# (the Django API), frontend (nginx + the built Vue SPA). Host-only
# addressing must stay inside 192.168.56.0/21 -- VirtualBox refuses other
# ranges by default.
#
# The host itself sits on this network as 192.168.56.1, so postgres on db
# and the API on backend are reachable from the host directly, with no port
# forwarding. The forwarded ports below exist only for the browser-facing
# entry point (and one debug port straight at the API).
#
# All three nodes run bento/ubuntu-24.04 (Python 3.12, Django 6.1's
# requirement) with one exception worth naming: there used to be a fourth
# node here, pk, pinned to 18.04 because it ran a second, older Django. pk's
# maths is now an in-process package inside backend/ -- see backend/pk/ --
# so that node, its box, and its separate Django are gone, not just
# relocated.
#
# Defined in boot order, which matters here: backend's provision waits for
# postgres before running migrations, and frontend's waits for the backend
# API before its health check, so each node coming up after the one it
# depends on means a plain `vagrant up` mostly just works without every
# script re-polling from a cold start. Each script still waits rather than
# assumes, because `vagrant up <single-node>` and `vagrant provision
# <single-node>` both skip that ordering entirely.

Vagrant.configure("2") do |config|

  servers = [
    {
      :hostname => "db",
      :box => "bento/ubuntu-24.04",
      :ip => "192.168.56.10",
      :ssh_port => 2200,
      :memory => 1024,
      :forwarded => [],
    },
    {
      :hostname => "backend",
      :box => "bento/ubuntu-24.04",
      :ip => "192.168.56.11",
      :ssh_port => 2201,
      :memory => 1024,
      # Not needed by the app -- frontend's nginx reaches this VM over the
      # private network. Here so the API can be curled from the host while
      # debugging, without going through nginx on the frontend VM.
      :forwarded => [{ :guest => 8000, :host => 8001 }],
    },
    {
      :hostname => "frontend",
      :box => "bento/ubuntu-24.04",
      :ip => "192.168.56.12",
      :ssh_port => 2202,
      # 1024 is enough to run nginx but not to build the SPA: `npm ci` plus
      # a vite production build is the memory high-water mark of the whole
      # project and gets OOM-killed on 1GB.
      :memory => 2048,
      # The entry point. nginx on the guest serves the SPA and proxies the
      # API to the backend VM, both from port 80. The host port doesn't
      # have to be 8000 -- frontend/src/api.js's baseURL is the page's own
      # origin, not a hardcoded host:port -- but 8000 is the conventional
      # choice and what the README documents; auto_correct below means a
      # busy host port 8000 shifts rather than failing the whole `vagrant
      # up`, and the app still works on whatever port it lands on.
      :forwarded => [{ :guest => 80, :host => 8000 }],
    },
  ]

  servers.each do |machine|
    config.vm.define machine[:hostname] do |node|
      node.vm.box = machine[:box]
      node.vm.hostname = machine[:hostname]
      node.vm.network :private_network, ip: machine[:ip]
      node.vm.network "forwarded_port", guest: 22, host: machine[:ssh_port], id: "ssh"

      machine[:forwarded].each do |port|
        # auto_correct so a host port already in use shifts rather than
        # failing the whole `vagrant up`. Watch for the correction warning
        # if you want the app specifically at :8000 -- it still works on
        # whatever port it lands on either way.
        node.vm.network "forwarded_port",
                        guest: port[:guest], host: port[:host], auto_correct: true
      end

      node.vm.provision "shell", path: "provisions/common.sh"
      node.vm.provision "shell", path: "provisions/#{machine[:hostname]}.sh"

      node.vm.provider :virtualbox do |vb|
        vb.name = machine[:hostname]
        vb.customize ["modifyvm", :id, "--memory", machine[:memory]]
        vb.customize ["modifyvm", :id, "--cpus", 1]
      end
    end
  end

end
