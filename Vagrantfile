# -*- mode: ruby -*-
# vi: set ft=ruby :

# Three nodes on a host-only private network. Host-only addressing must stay
# inside 192.168.56.0/21 -- VirtualBox refuses other ranges by default.
#
# The host itself sits on this network as 192.168.56.1, so postgres on db and
# the pk service are reachable from the host directly, with no port
# forwarding. The forwarded ports below exist only for the browser-facing
# entry point.
#
# Box choice is per node, and both boxes are pinned by what Django 6.1
# (web/requirements.txt) demands at each end:
#
#   web -- 24.04. Django 6.1 needs Python 3.12; 18.04 ships 3.6. That
#          mismatch is why there was never a working web.sh.
#   db  -- 24.04. Django 6.1 needs PostgreSQL 15 or later, and bionic's
#          newest is 10.23 -- `migrate` fails outright with
#          NotSupportedError. Noble ships 16.
#   pk  -- 18.04. Nothing forces this one: pk talks to no database, and it
#          pins Django 3.2 precisely because 3.6 is what this box ships.
#          Left where it is, working, rather than upgraded for symmetry.
#
# Bionic is past end of life but is still served from archive.ubuntu.com, so
# `apt-get update` on the pk node still resolves.

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
      :hostname => "pk",
      :box => "bento/ubuntu-18.04",
      :ip => "192.168.56.11",
      :ssh_port => 2201,
      :memory => 1024,
      # Not needed by the app -- web calls pk over the private network. Here
      # so pk's endpoints can be poked from the host while debugging.
      :forwarded => [{ :guest => 8001, :host => 8001 }],
    },
    {
      :hostname => "web",
      :box => "bento/ubuntu-24.04",
      :ip => "192.168.56.12",
      :ssh_port => 2202,
      # 1024 is enough to run the app but not to build it: `npm ci` plus a
      # vite production build is the memory high-water mark of the whole
      # project and gets OOM-killed on 1GB.
      :memory => 2048,
      # The entry point. nginx on the guest serves the SPA and the API from
      # one origin on 8000; the host port must also be 8000, because
      # web/frontend/src/api.js has a hardcoded baseURL of
      # http://localhost:8000 and the browser resolves that against the host.
      :forwarded => [{ :guest => 8000, :host => 8000 }],
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
        # failing the whole `vagrant up`. If 8000 gets corrected, the SPA
        # will not be able to reach its API -- see the note above -- so
        # watch for the correction warning.
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
