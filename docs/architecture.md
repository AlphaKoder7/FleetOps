# Architecture

Host controller → fleetops-lb:18080 → fleetops-web-{1,2}:18081. Three Ubuntu 24.04 KVM guests, each initially 1 vCPU / 1 GiB / 8 GiB sparse disk. Dedicated NAT network; discovered IPs. Host and load balancer are single points of failure. No guest resources exist yet.
