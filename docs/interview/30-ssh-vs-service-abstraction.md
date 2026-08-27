# SSH vs Service Abstraction

**Question:** Why is SSH allowed if OpsPilot removed ServiceSSH?

**Answer:** SSH is a transport, not an application capability. The application asks to restart a
semantic service. An operator profile resolves that intent to a fixed systemd unit or fixed script
mapping, and Ansible may use SSH underneath. The model and API never control connectivity or command
construction, so transport support does not recreate arbitrary remote execution.
