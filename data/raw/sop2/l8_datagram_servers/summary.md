# Summary: SOP2 lab 8 - Datagram protocols and multithreaded servers

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP2 lab 8 - Datagram protocols and multithreaded servers

Source: https://sop.mini.pw.edu.pl/en/sop2/lab/l8/

- Lab id: `sop2/l8`
- Tutorial sections: 9
- Tasks: 2
- Source files: 6

## Topics

`SOCK_DGRAM`, `unix`, `AF_INET6`, `udp`, `listen`, `recvfrom`, `sendto`, `recv`, `send`

## Tutorial outline

  - **Datagram Protocols** - ## Datagram Protocols Unlike stream protocols such as TCP, in datagram protocols we transmit packets of data, that is, _datagrams_. As with stream protocols, we will study them in the context of both network (UDP) and local sockets (UNIX).
    - **UNIX** - ### UNIX A local datagram socket is created similarly to a stream socket, simply by specifying `SOCK_DGRAM` as the protocol type: ```C socket(PF_UNIX, SOCK_DGRAM, 0) ``` All rules related to local sockets apply (`man 7 unix`). It is worth noting that, unlike network datagram sockets (UDP), local one
    - **UDP** - ### UDP A network datagram socket, i.e. a UDP socket, is created analogously to TCP - it is enough to change the type to `SOCK_DGRAM`, for example: ```C socket(AF_INET, SOCK_DGRAM, 0) ``` for an IPv4 socket (`AF_INET6` for IPv6). To learn more about UDP, be sure to read `man 7 udp` and the [lecture 
    - **Communication** - ### Communication Datagram protocols are connectionless - we do not call `connect` on the client side, nor `listen` and `accept` on the server side. Instead, we simply have two functions for sending and receiving data: ```C ssize_t recvfrom(int socket, void *restrict buffer, size_t length, int flags
  - **Task** - ## Task Goal: Write client and a server program that communicate over UDP socket. Client task is to send a file divided into proper size datagrams to the server. Server prints out the received data without information about the source. Each packet send to server must be confirmed with return message
  - **Multithreaded Servers** - ## Multithreaded Servers During the previous lab, we practiced writing servers using only one thread. Such architecture makes a lot of sense when we need to conserve resources and expect a relatively low load. Often, however, our server must handle a very large number of requests. In such a situatio
  - **Example Tasks** - ## Example Tasks Complete the sample exercises. You will have more time and starter code during the lab session, but completing the tasks below on your own means you are well prepared. - [Task 1](https://sop.mini.pw.edu.pl/en/sop2/lab/l8/example1/) ~100 ~~days~~ minutes - [Task 2](https://sop.mini.p
  - **Source codes presented in this tutorial** - ## Source codes presented in this tutorial - [l8-1_client.c](l8-1_client.c) - [l8-1_server.c](l8-1_server.c) - [l8_common.h](l8_common.h)
  - **Other references** - ## Other references - <https://cs341.cs.illinois.edu/coursebook/Networking#layer-4-udp>

## Tasks

- **example1: UDP Test Task** - 4 stages
  1. The server program takes one argument: the port number. The program waits for datagrams on the given port. Messages have the form `<X> <Y> <P> <division name>`. `X` and `Y` are map coordinates (natural numbers in the range from 0 to 99), while `<division name>` is text no longer than 128 characters.
  2. In such a fierce battle, there is considerable confusion even within headquarters itself. Incoming messengers throw reports onto a stack by the entrance, from where they are picked up by four adjutants, who use them to update the headquarters maps. Implement a thread pool of adjutants. After receivi
  3. Add updates to the headquarters maps. Create a shared array of division names among the threads, of size `DIVISION_NAMES_SIZE` equal to 128. After receiving a new report, an adjutant works on it (that is, sleeps for 10 ms). Then they check whether the division name is already in the array. If not, t
  4. Add Napoleon’s thread. Remember the addresses from which the last report for a given division arrived. Every 30 ms, the Emperor of the French prints the state of the map. Then he chooses a random allied division and sends it an order of the form `<X> <Y> <P> <division name>`.
- **example2: UDP Test Task** - 7 stages
  1. Implement a UDP server that accepts messages in the following format:
  2. 16 bytes containing the login (padded with zeros if needed) --- one of the logins listed in the `LOGINS` array,
  3. 8 bytes containing the command (padded with zeros if needed) --- `RUN`, `EXIT`, `PAUSE`, `COMPUTE`, `LIST`, or `GATHER`,
  4. optional command parameters. For the `COMPUTE` command, the parameters consist of a non-empty sequence of pairs of 4-byte unsigned integers (`uint32_t`). The other commands do not take any additional parameters. All numbers are encoded in network byte order. A message may be at most `MSG_MAX` bytes 
  5. The `COMPUTE` command requests new jobs for estimating the value of π, using the function `double compute_pi(const int count, const int* seed)` provided in the starter code. For each pair of numbers in the message, create a new job. The first number is the sample count and must not exceed 10 million
  6. Implement a thread pool consisting of `THREADS` worker threads for computing π. Each worker should take a job from the front of the queue (with proper synchronization) and process at most 1000 samples. If the job still has samples remaining afterward, put it back at the end of the queue with the rem
  7. When the server receives the `PAUSE` command, the thread pool should stop processing jobs belonging to that user until a `RUN` command is received. If a `PAUSE` command is received for a user who is already paused, or a `RUN` command is received for a user who is not paused, print the message `<user

## Source files

- `src/sop-eden-init.c` (c)
- `src/sop-eden-test.sh` (bash)
- `src/sop-eden.c` (c)
- `src/l8-1_client.c` (c)
- `src/l8-1_server.c` (c)
- `src/l8_common.h` (c)
