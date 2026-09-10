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
# Box choice is per node and is driven by the Python each one needs:
#
#   db, pk -- 18.04 (Python 3.6). Past end of life, but bionic is still on
#             archive.ubuntu.com and `apt-get update` still resolves, and pk
#             pins Django 3.2 specifically because 3.6 is what this box
#             ships. Left alone: it works, and moving it would mean
#             upgrading pk's Django for no gain. See pk/requirements.txt.
#   web    -- 24.04 (Python 3.12). web/requirements.txt pins Django 6.1,
#             which requires Python 3.12 or newer, so this node *cannot*
#             stay on 18.04 -- that mismatch is why there was never a
#             working web.sh.

Vagrant.configure("2") do |config|

  servers = [
    {
      :hostname => "db",
      :box => "bento/ubuntu-18.04",
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
