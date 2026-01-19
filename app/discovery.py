"""
mDNS service discovery for Echonet.

Advertises Echonet as a service on the local network so LLMs and other
services can automatically discover available microphone instances.
"""

from __future__ import annotations

import logging
import socket
from typing import Optional

log = logging.getLogger("echonet.discovery")

# Try to import zeroconf, but make it optional
try:
    from zeroconf import ServiceInfo, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    log.warning("zeroconf not installed. mDNS discovery will be disabled. Install with: pip install zeroconf")


class DiscoveryService:
    """Manages mDNS service advertisement for Echonet."""
    
    def __init__(
        self,
        instance_name: str,
        host: str,
        port: int,
        zone: str = "",
        subzone: str = "",
    ):
        self.instance_name = instance_name
        self.host = host
        self.port = port
        self.zone = zone
        self.subzone = subzone
        
        self.zeroconf: Optional[Zeroconf] = None
        self.service_info: Optional[ServiceInfo] = None
    
    def start(self) -> bool:
        """Start advertising the service via mDNS."""
        if not ZEROCONF_AVAILABLE:
            log.warning("Cannot start mDNS discovery: zeroconf not available")
            return False
        
        try:
            # Get local IP address
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # Create service type (similar to Bellphonics pattern)
            service_type = "_echonet._tcp.local."
            
            # Create service name with instance
            service_name = f"{self.instance_name}.{service_type}"
            
            # Service properties (metadata)
            properties = {
                "version": "0.1.0",
                "type": "microphone",
                "zone": self.zone,
                "subzone": self.subzone,
                "capabilities": "asr,routing,sessions,state",
            }
            
            # Create ServiceInfo
            self.service_info = ServiceInfo(
                service_type,
                service_name,
                addresses=[socket.inet_aton(local_ip)],
                port=self.port,
                properties=properties,
                server=f"{self.host}.local.",
            )
            
            # Register the service
            self.zeroconf = Zeroconf()
            self.zeroconf.register_service(self.service_info)
            
            log.info(
                f"mDNS service registered: {service_name} at {local_ip}:{self.port} "
                f"(zone={self.zone}, subzone={self.subzone})"
            )
            return True
            
        except Exception as e:
            log.error(f"Failed to start mDNS discovery: {e}")
            return False
    
    def stop(self):
        """Stop advertising the service."""
        if self.zeroconf and self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                log.info("mDNS service unregistered")
            except Exception as e:
                log.error(f"Error stopping mDNS discovery: {e}")
        
        self.zeroconf = None
        self.service_info = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
