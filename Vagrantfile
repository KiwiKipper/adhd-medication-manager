# -*- mode: ruby -*-
# vi: set ft=ruby :

# Three VMs, one per tier: db (postgres), backend (Django API), frontend
# (nginx + the built Vue SPA).
#
# The IPs have to stay inside 192.168.56.0/21 or VirtualBox refuses them.
# The host sits on this network as 192.168.56.1, so postgres and the API are
# reachable from the host without port forwarding; the forwarded ports below
# are only for the browser entry point and one debug port at the API.
#
# Boot order matters. backend's provision waits for postgres before running
# migrations, and frontend's waits for the API, so a plain `vagrant up` in
# this order mostly just works. Each script still polls rather than assumes,
# because `vagrant up <one-node>` skips the ordering entirely.

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
      # Only so the API can be curled from the host while debugging. The app
      # doesn't need it: nginx reaches this VM over the private network.
      :forwarded => [{ :guest => 8000, :host => 8001 }],
    },
    {
      :hostname => "frontend",
      :box => "bento/ubuntu-24.04",
      :ip => "192.168.56.12",
      :ssh_port => 2202,
      # 2048 because `npm ci` plus a vite production build gets OOM-killed
      # on 1GB. nginx alone would be fine on less.
      :memory => 2048,
      # The entry point: nginx serves the SPA and proxies the API, both on
      # port 80. The host port doesn't have to be 8000 (api.js uses the
      # page's own origin), but that's what the README says to use.
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
        # auto_correct so a busy host port shifts instead of failing the
        # whole `vagrant up`. Watch for the warning if you want :8000
        # specifically.
        node.vm.network "forwarded_port",
                        guest: port[:guest], host: port[:host], auto_correct: true
      end

      # The per-node script name comes from the hostname, so scripts/ must
      # hold db.sh, backend.sh and frontend.sh under exactly those names.
      node.vm.provision "shell", path: "scripts/common.sh"
      node.vm.provision "shell", path: "scripts/#{machine[:hostname]}.sh"

      node.vm.provider :virtualbox do |vb|
        vb.name = machine[:hostname]
        vb.customize ["modifyvm", :id, "--memory", machine[:memory]]
        vb.customize ["modifyvm", :id, "--cpus", 1]
      end
    end
  end

end
