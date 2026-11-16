# Summary: SOP2 lab netcat - Netcat

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP2 lab netcat - Netcat

Source: https://sop.mini.pw.edu.pl/en/sop2/lab/netcat/

- Lab id: `sop2/netcat`
- Tutorial sections: 6
- Tasks: 0
- Source files: 0

## Tutorial outline

- **Introduction** - # Introduction `netcat` is a program that can be used to perform a variety of network connections (TCP, UDP and others) and send data read from `stdin` to the connection as well as printing the data from the network connection to `stdout`. You can use netcat to communicate with programs that use pla
- **netcat versions** - # netcat versions The `netcat` program comes in several different version depending on the operating system installed. All popular versions can communicate using TCP and UCP sockets, although they differ in case of some advanced operations. In major Linux distributions you usually find one of three 
- **netcat usage** - # netcat usage The full description of `netcat` is available in the manual. Below we present the most common usage examples. In majority of systems `netcat` is available under the command `nc`, sometimes also `netcat` or `ncat`.
  - **TCP** - ## TCP By default if there are no switches specifying the protocol to be used `netcat` operates in TCP mode: - `nc <host> <port>` --- connects as a TCP client to the server given as the argument - `nc -l -s <address> -p <port>` --- starts a server socket listening on the given port, `-s` is optional
  - **UDP** - ## UDP To use `netcat` in UCP mode option `-u` is used: - `nc -u <host> <port>` --- creates a UDP socket bound to a random port and sends all data from `stdin` to the address given, - `nc -u -l -s <address> -p <port>` --- creates udp socket bound to the specified address and port and waits for data 
  - **UNIX** - ## UNIX - `nc -U <path>` --- connects to a given unix domain socket (stream) - `nc -l -U <path>` --- waits for connections on the given unix domain socket (stream) - `nc -U -u <path>` --- sends data to a given unix domain socket (datagram) - `nc -l -U -u <path>` --- waits for data on the given unix 
