# Summary: SOP2 lab 5.5 - POSIX Queues (extra topic)

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP2 lab 5.5 - POSIX Queues (extra topic)

Source: https://sop.mini.pw.edu.pl/en/sop2/lab/l5_5/

- Lab id: `sop2/l5_5`
- Tutorial sections: 16
- Tasks: 4
- Source files: 2

## Topics

`mq_overview`, `mq_open`, `O_RDONLY`, `O_WRONLY`, `O_RDWR`, `O_CREAT`, `O_NONBLOCK`, `NULL`, `O_EXCL`, `mqd_t`, `mq_close`, `mq_unlink`, `mq_getattr`, `mq_setattr`, `mq_send`, `mq_receive`, `MQ_PRIO_MAX`, `EAGAIN`, `mq_timedsend`, `mq_timedreceive`, `ETIMEDOUT`, `CLOCK_REALTIME`, `clock_getres`, `mq_timed`, `mq_`, `mq_notify`, `sigevent`, `SIGEV_SIGNAL`, `SIGRTMIN`, `sigaction`, `SA_SIGINFO`, `sethandler`, `mq_handler`, `SIGEV_THREAD`, `EINVAL`, `EBUSY`, `kill`, `TEMP_FAILURE_RETRY`, `waitpid`, `SIGCHLD`, `CHILD_COUNT`, `ROUNDS`, `child_function`, `handle_messages`, `register_notification`, `exit`, `spawn_child`

## Tutorial outline

- **Tutorial 5.5 - POSIX Message Queues** - # Tutorial 5.5 - POSIX Message Queues > This tutorial covers topics not checked during graded laboratories. > Still, message queues are useful, so we leave it here and encourage everyone to read it.
  - **POSIX Queue Operations** - ## POSIX Queue Operations The topic of message queues is noticeably less extensive than that of pipes/FIFOs, and this tutorial is also shorter. POSIX message queues don’t suffer from issues with simultaneous reading and writing, guarantee atomic writes even for large messages, provide distinct messa
    - **Creating, Opening, and Removing Queues** - ### Creating, Opening, and Removing Queues Queues are identified by a name (defined by the programmer) `/<name>`, e.g., `/queue`. To create and open a queue, use the `mq_open` function (`man 3p mq_open`): ``` mqd_t mq_open(const char *name, int oflag, ...); ``` - `name` is the name of the queue, - `
    - **Queue Attributes** - ### Queue Attributes Queues store their attributes in a `mq_attr` structure, discussed in the previous section (see `mq_open`, `O_CREAT` flag). You can retrieve queue attributes using `mq_getattr` (`man 3p mq_getattr`): ``` int mq_getattr(mqd_t mqdes, struct mq_attr *mqstat); ``` - `mqdes` is the de
    - **Sending and Receiving Messages** - ### Sending and Receiving Messages So far, we have used `read` and `write` to handle I/O with files and pipes. Message queues, however, use their own functions: `mq_send` and `mq_receive` (`man 3p mq_send`, `man 3p mq_receive`). Let’s look at their definitions: ``` int mq_send(mqd_t mqdes, const cha
    - **Notifications** - ### Notifications POSIX provides the ability to asynchronously notify processes about incoming messages to an empty queue. To register a process for notification, use the `mq_notify` function (`man 3p mq_notify`): ``` int mq_notify(mqd_t mqdes, const struct sigevent *notification); ``` - `mqdes` is 
    - **Notes** - ### Notes 1. You must link the `librt` library when compiling programs that use POSIX message queues. 2. If you open an existing queue, it may already contain data. You should not assume it is empty. To ensure a clean state, delete the queue before recreating it.
  - **Tasks with Solutions** - ## Tasks with Solutions
    - **Task 1: Signal-Based Notification** - ### Task 1: Signal-Based Notification Write a program that simulates a simple version of *bingo*. The parent process randomly draws numbers, and the players are its child processes. Communication between them takes place via POSIX message queues. The parent process creates `n` child processes (`0 < 
      - **Task Solution** - #### Task Solution New manpages: - `man 7 mq_overview` - `man 3p mq_open` - `man 3p mq_close` - `man 3p mq_unlink` - `man 3p mq_getattr` - `man 3p mq_setattr` - `man 3p mq_send` - `man 3p mq_receive` - `man 3p mq_notify` - `man 7 sigevent` ```c #define _GNU_SOURCE #include <errno.h> #include <mqueue
      - **Notes and Questions** - #### Notes and Questions - Pay attention to the use of the pointer sent with the signal. The signal handler function prototype includes an additional `siginfo_t*` parameter, and the `SA_SIGINFO` flag is used when installing the handler to enable pointer passing. Note that we are not sending this sig
    - **Task 2: Thread-based Notification** - ### Task 2: Thread-based Notification Write a program simulating conversations on a Roman forum. Define a constant `CHILD_COUNT`. The parent process creates `CHILD_COUNT` queues, opens them in non-blocking mode, and spawns `CHILD_COUNT` child processes. Each child receives a randomly generated name.
      - **Solution** - #### Solution ```c #include <errno.h> #include <fcntl.h> #include <mqueue.h> #include <pthread.h> #include <signal.h> #include <stdio.h> #include <stdlib.h> #include <sys/wait.h> #include <unistd.h> #define CHILD_COUNT 4 #define QUEUE_NAME_MAX_LEN 32 #define CHILD_NAME_MAX_LEN 32 #define MSG_SIZE 64
      - **Notes and Questions** - #### Notes and Questions - Why do we break the `mq_receive` loop on `EAGAIN`? **Answer:** This error means the queue is empty and there’s nothing more to read. - Why does `child_function` call `handle_messages` and not just `register_notification`? **Answer:** Because if messages are already in the 
  - **Example Exercises** - ## Example Exercises Complete the sample exercises. You will have more time and starter code during the lab session, but completing the tasks below on your own means you are well prepared. - [Exercise 1](https://sop.mini.pw.edu.pl/en/sop2/lab/l5_5/example1/) ~90 minutes - [Exercise 2](https://sop.mi
  - **Source Code from the Tutorial** - ## Source Code from the Tutorial - [l5_5-1.c](l5_5-1.c) - [l5_5-2.c](l5_5-2.c)

## Tasks

- **example1: Task on POSIX message queues** - 4 stages
  1. The server creates its queues and displays the names of the queues. After 1 second, it destroys those queues and terminates. The client process creates its own queue, waits for 1 second, destroys its queue, and terminates.
  2. Server reads the first message from `PID_s` queue. Sends the first answer back to the client. Ignores all errors. The client reads 2 integers from stdin and sends a single message to the server. It waits for the result and displays it.
  3. The server handles all queues and calculates the proper results. Terminates at `SIGINT`. The client sends the messages until `EOF` is read or reply timeout occurs.
  4. The queues should be removed on program termination. Full error handling.
- **example2: Task on POSIX message queues** - 4 stages
  1. The main process creates N workers, who after performing a random sleep (500 ms - 2000 ms) finish their work. At the start, the server prints `"Server is starting..."` and after all workers have finished, it prints `"All child processes have finished."` Workers print `"[{worker_pid}] Worker ready!"`
  2. The server creates `5 * N` tasks at random time intervals (`T₁` to `T₂` ms) and adds them to the queue. The server informs when a task is added: `"New task queued: [{v1}, {v2}]"` or if the queue is full: `"Queue is full!"`. Workers, upon receiving a task, print: `"[{worker_pid}] Received task [{v1},
  3. Workers send results to the server through their individual queues and inform about it on standard output: `"[{worker_pid}] Result sent [{value}]"` The server receives results and prints: `"Result from worker {worker_pid}: {value}"`
  4. The main process continues to create tasks until it receives a `SIGINT` signal, after which it informs workers to stop (via the queue). The server waits for workers to finish their current tasks before terminating. Workers finish after receiving the stop notification from the server (they complete o
- **example3: Task on POSIX message queues** - 15 stages
  1. The main process (game coordinator) correctly creates new processes based on the given names of the children and waits for their termination.
  2. There is no predetermined limit (apart from system resources) on the number of children participating in the game.
  3. At a minimum, to start the game, there must be at least one child. Each child knows only their name and the child's PID from which they listen. In the case of the first child, it is the PID of the coordinator.
  4. A child displays the message `[{PID}] {name} has joined the game!`, waits a random time between `T₁` and `T₂`, and exits with the message `[{PID}] {name} has left the game!`.
  5. A child, upon joining the game, creates a new queue named `"sop_cwg_{PID}"`.
  6. The child knows only the PID of the preceding child - this tells them which queue to receive messages from.
  7. Typing `start {message_to_pass}` starts sending word-by-word the given message to the first child.
  8. Only the first child receives the message from the coordinator for this stage.
  9. Upon receiving a word, it prints it to standard output `[{PID}] {name} got the message: '{word}'`.
  10. Words are transmitted between the children and then returned back to the coordinator.
  11. For each letter of the word, there is a `P%` chance that the letter will be changed to some random Latin letter.
  12. The coordinator prints the received message on standard output. All used resources are correctly released.
  13. After receiving the `SIGINT` signal, all children quit the game.
  14. The coordinator displays the part of the message he has already received and exits.
  15. You can use a timeout for messages to avoid a deadlock in this stage. ---
- **example4: Task on POSIX message queues** - 4 stages
  1. The server opens queue `"chat_{server_name}"`, reads from it, and displays in a loop a read message on the standard output as: `"[{msg_prio}] {msg_content}"`. The client opens `"chat_{server_name}"` and sends its name there with the proper message priority.
  2. The client creates its queue `"chat_{client_name}"` at the start. The server opens a client's queue after receiving the client's name (sent as a raw C-string with priority 0) and stores information about connected clients (max 8 clients connected at once). On a client connection, the server displays
  3. A client sends lines from the standard input to the server. The server receives data from clients using `mq_notify`. It displays them on the standard output formatted as: `"[{sender_name}] {message}"` and broadcasts them to all clients in the same format. The server also supports typing messages, wh
  4. The server supports closing on `Ctrl-C`. It sends information about its closing using an "empty" message with the proper priority. Upon receiving the server closing message, clients display: `"Server closed the connection"` and terminate. Upon receiving the client closing message, the server display

## Source files

- `src/l5_5-1.c` (c)
- `src/l5_5-2.c` (c)
