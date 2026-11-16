# Summary: SOP2 lab 7 - sockets and epoll

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP2 lab 7 - sockets and epoll

Source: https://sop.mini.pw.edu.pl/en/sop2/lab/l7/

- Lab id: `sop2/l7`
- Tutorial sections: 6
- Tasks: 4
- Source files: 5

## Topics

`epoll`, `socket`, `unix`, `tcp`, `bind`, `listen`, `connect`, `accept`, `epoll_create`, `epoll_ctl`, `epoll_wait`, `freeaddrinfo`, `gai_strerror`, `bulk_read`, `TEMP_FAILURE_RETRY`, `epoll_pwait`

## Tutorial outline

- **Tutorial 7 - Sockets and epoll** - # Tutorial 7 - Sockets and epoll > In this tutorial we use `epoll` functions family to wait on multiple descriptors. `epoll` is not a part of POSIX, but Linux extension. If you want to write portable code, you should look at `select` or `poll` functions - which are standarized, but have worse perfor
  - **Task on local + TCP sockets** - ## Task on local + TCP sockets Write simple integer calculator server. Data send to server consists of: - operand 1 - operand 2 - result - operator (+,-,*,/) - status all converted to 32 bit integers in an array. Server calculates the results of operation (+,-,*,/) on operands and sends the result b
    - **Solution** - ### Solution What you must know: ``` man 7 socket man 7 epoll man 7 unix man 7 tcp man 3p socket man 3p bind man 3p listen man 3p connect man 3p accept man 2 epoll_create man 2 epoll_ctl man 2 epoll_wait man 3p freeaddrinfo (obie funkcje, getaddrinfo też) man 3p gai_strerror ``` Pay closer attention
  - **Sample task** - ## Sample task Complete the sample exercises. You will have more time and starter code during the lab session, but completing the tasks below on your own means you are well prepared. - [Exercise 1](https://sop.mini.pw.edu.pl/en/sop2/lab/l7/example1/) ~60 minutes - [Exercise 2](https://sop.mini.pw.ed
  - **Source codes presented in this tutorial** - ## Source codes presented in this tutorial - [l7-1_client_local.c](l7-1_client_local.c) - [l7-1_client_tcp.c](l7-1_client_tcp.c) - [l7-1_server.c](l7-1_server.c) - [l7_common.h](l7_common.h)
  - **Other references** - ## Other references - <http://cs341.cs.illinois.edu/coursebook/Networking#layer-4-tcp-and-client> - <http://cs341.cs.illinois.edu/coursebook/Networking#layer-4-tcp-server> - <http://cs341.cs.illinois.edu/coursebook/Networking#non-blocking-io>

## Tasks

- **example1: Task on network** - 4 stages
  1. Server accepts only one connection, reads text data from the client and prints it on the stdout. Client connects and sends text data
  2. Server accepts many connections, counts the sum of digits and sends the numer (int16_t) back to the client, client prints the result
  3. Server properly handles C-c, prints maximum sum.
  4. All types of broken connection on the socket are properly checked and handled.
- **example2: Task on network** - 10 stages
  1. Implement accepting a single connection to the server. The server accepts one argument: the port number. Example server execution: ```shell ./sop-hre 8888 ``` After starting, the server waits for a single TCP connection. After establishing a connection, the server prints `Client connected`, closes t
  2. Implement connections from multiple clients. After a client connects, send them back a message: `Welcome, elector!` Then, print each message the client sends to the server on `stdout`. Use `epoll` to implement this stage (or, alternatively, `ppoll` or `pselect`). Remember to correctly handle disconn
  3. Implement the voting process and keep a list of connected electors. When a new client connects, wait for a single digit (in the range [1, 7]). This digit is the number of the elector connecting to the server. If a different character is received from the client, close their connection. While the ser
  4. Implement an additional thread sending out UDP messages. The program should now accept two arguments in total:
  5. the TCP server port
  6. the UDP client port Example server execution: ```shell ./sop-hre 8888 9999 ``` All functionality from the previous stages should still work. Upon starting the server, create an additional thread with a UDP client that sends a message with the current election results each second to the given port on
  7. Handle the `SIGINT` signal. After receiving it:
  8. Close all active connections with the electors
  9. Free all resources, including the UDP thread
  10. Count and print the votes for each candidate.
- **example3: Task on network** - 23 stages
  1. Implement handling of a single client connecting to a TCP server. The server accepts the port number as a command-line argument. Example server execution: ```shell ./server 8888 ``` After starting, the server listens for incoming client connections. Once connected to the first client, it waits to re
  2. Implement handling of multiple clients and receiving data.
  3. When a new client connects, they are added to the current list of clients.
  4. The maximum number of clients is 4.
  5. If the maximum number of clients is reached, new connections should be rejected.
  6. Whenever the server receives a 4-byte message from any client, it prints it to the terminal. Use the epoll function to implement this step (alternatively, you may use pselect or ppoll). > ⚠️ **Note: In this step, you do not need to correctly handle client disconnections.**
  7. Add to the server an array that stores information about which side each city belongs to.
  8. Initially, all cities belong to the Greeks.
  9. Each time the server receives a message in the format: ``` pXX\n ``` or ``` gXX\n ``` where `XX` is a two-digit number representing a city identifier, it indicates that city `XX` now belongs to the Persians or the Greeks, respectively.
  10. If a city’s ownership hasn’t changed, take no action.
  11. If the city’s owner has changed:
  12. update the city ownership array,
  13. broadcast the received message to all other connected clients. Assumptions:
  14. You still do not need to handle client disconnections at this stage.
  15. All incoming messages can be assumed to be in the correct format.
  16. Upon receiving a `SIGINT` signal, the server should:
  17. close all connections,
  18. print out which side each city belongs to,
  19. free resources and terminate. Add proper handling for client disconnections in the following cases:
  20. Reading from a client descriptor returns a message of length 0.
  21. Writing to a client descriptor raises an `EPIPE` error.
  22. The message received from the client is not in the correct format or the city number is outside the [1, 20] range.
  23. The server receives a Control-C (C-c). > ⚠️ **Note: Disconnected clients free up space for new incoming clients.**
- **example4: Task on network** - 28 stages
  1. Implement connecting to the TCP server.
  2. The client accepts two arguments: server address and port number.
  3. Example client execution: ```shell ./client 127.0.0.1 8888 ```
  4. After starting:
  5. Connect to the specified server using the TCP protocol.
  6. After establishing a connection:
  7. Send a 4-character message read from `stdin` to the server.
  8. Close the connection and terminate the program.
  9. Implement `stdin` command handling and message sending.
  10. After connecting to the server, wait for commands on `stdin`.
  11. Support the following commands:
  12. `e` (exit) – close the connection and terminate the program.
  13. `m XXX` (message) – send a 4-character message (3 characters + newline) to the server, where `XXX` are any 3 characters.
  14. `t XX` (travel) – randomly choose one of the two letters {g, p}, and send: ``` YXX\n ``` to the server, where `Y` is the randomly selected letter, and `XX` is a two-digit number in the range [1, 20]. For single-digit numbers (1–9), use a leading 0. If the number is outside of the range, print an err
  15. `o` (owners) – print the ownership of each city (described below).
  16. Keep an array that stores which side (Greek or Persian) owns which city.
  17. Initialize all cities with unknown ownership.
  18. After sending a message like `gXX\n` via the `t` command, mark city `XX` as belonging to the Greeks.
  19. Likewise, for messages starting with `pXX\n`, mark the corresponding city as Persian.
  20. In addition to reading from `stdin`, also handle input from the server socket.
  21. You can use `epoll` (or `ppoll` or `pselect`) to add both `STDIN_FILENO` and the server socket descriptor to the monitored set.
  22. The server may send messages to the client in the exact same format as those generated by the `t XX` command.
  23. When such a message is received from the server, treat it exactly the same way as one generated locally by the `t` command (i.e., update city ownership).
  24. After receiving a SIGINT signal:
  25. Print the current owner of each city.
  26. Close any active connections.
  27. Free all resources.
  28. Exit the program.

## Source files

- `src/l7-1_client_local.c` (c)
- `src/l7-1_client_tcp.c` (c)
- `src/l7-1_server.c` (c)
- `src/l7_common.h` (c)
- `src/sop2l8e3-4.zip` (zip)
