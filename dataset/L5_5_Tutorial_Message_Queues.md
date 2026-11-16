# Tutorial 5.5: POSIX Message Queues

*Topic: L5.5 — POSIX message queues (tutorial)*


This tutorial covers topics not checked during graded laboratories. Still, message queues are useful, so we leave it here and encourage everyone to read it.

## POSIX Queue Operations

The topic of message queues is noticeably less extensive than that of pipes/FIFOs, and this tutorial is also shorter.

POSIX message queues don’t suffer from issues with simultaneous reading and writing, guarantee atomic writes even for large messages, provide distinct message boundaries, and support priorities. These features make the topic relatively simple, with potential difficulties mostly limited to handling queue event notifications.

The main focus of this session is POSIX message queues, but the tasks will also involve elements practiced earlier, such as threads, processes, and signals.

The manual `man 7 mq_overview` contains a description of how queues work. The discussed functions are defined in the `<mqueue.h>` header file, and the interface is designed in a way that allows queues to be used similarly to file operations — it’s worth noting the parallels in how each function is defined and used.

POSIX queues are priority-based, meaning the order of messages is determined first by priority and then by send order.

### Creating, Opening, and Removing Queues

Queues are identified by a name (defined by the programmer) `/<name>`, e.g., `/queue`.

To create and open a queue, use the `mq_open` function (`man 3p mq_open`):

```c
mqd_t mq_open(const char *name, int oflag, ...);
```

- `name` is the name of the queue,
- `oflag` is a bitmask defining the access mode. Available options include:
  - `O_RDONLY`, `O_WRONLY`, `O_RDWR` — open for reading/writing/both,
  - `O_CREAT` — create the queue; this requires two additional arguments:
    - `mode_t mode`, which specifies access permissions, and
    - `mq_attr* attr`, a structure with 4 fields:
      - `mq_flags`, a bitmask (POSIX only defines the presence/absence of `O_NONBLOCK`, others are implementation-dependent),
      - `mq_maxmsg` — maximum number of messages in the queue,
      - `mq_msgsize` — maximum message size,
      - `mq_curmsgs` — current number of messages in the queue (ignored when creating the queue).

    You can also pass `NULL` as `attr`, and the queue will be created with default settings.
  - `O_EXCL` — used only with `O_CREAT`, it causes an error if a queue with the given name already exists,
  - `O_NONBLOCK` — sets the queue to non-blocking mode.

The function returns a message queue descriptor (`mqd_t`) or `(mqd_t)-1` on error.

Unused descriptors should be closed using `mq_close` (`man 3p mq_close`).

You can remove a queue by name using `mq_unlink`. Be cautious when attempting to remove a queue that is still open in another process. As noted in `man 3p mq_unlink`, unlinking only frees the name (e.g., so it can be reused). The queue is actually removed only after all associated descriptors are closed. Depending on the implementation, `mq_unlink` may block until other processes close their descriptors. On Linux (`man 3 mq_unlink`), however, it returns immediately.

Even in that case, a newly created queue with the same name will be a different queue.

### Queue Attributes

Queues store their attributes in a `mq_attr` structure, discussed in the previous section (see `mq_open`, `O_CREAT` flag). You can retrieve queue attributes using `mq_getattr` (`man 3p mq_getattr`):

```c
int mq_getattr(mqd_t mqdes, struct mq_attr *mqstat);
```

- `mqdes` is the descriptor of the open queue,
- `mqstat` is a pointer to an already allocated `struct mq_attr` variable, whose fields will be filled by the function.

To set queue attributes, use `mq_setattr` (`man 3p mq_setattr`):

```c
int mq_setattr(mqd_t mqdes, const struct mq_attr *restrict mqstat, struct mq_attr *restrict omqstat);
```

- `mqdes` is the descriptor of the open queue,
- `mqstat` points to the `mq_attr` structure with attributes you want to set,
- `omqstat` points to an already allocated `mq_attr` variable; its fields will be filled with values before the call to `mq_setattr`. You may also pass `NULL`.

IMPORTANT: The `mq_setattr` function only changes the `mq_flags` field. The other fields (`mq_maxmsg`, `mq_msgsize`, and `mq_curmsgs`) are immutable (set only during queue creation) and ignored by `mq_setattr`.

In practice, according to POSIX, the only changeable setting is the blocking/non-blocking I/O mode.

Both functions return 0 on success or -1 on failure.

### Sending and Receiving Messages

So far, we have used `read` and `write` to handle I/O with files and pipes. Message queues, however, use their own functions: `mq_send` and `mq_receive` (`man 3p mq_send`, `man 3p mq_receive`). Let’s look at their definitions:

```c
int mq_send(mqd_t mqdes, const char *msg_ptr, size_t msg_len, unsigned msg_prio);
ssize_t mq_receive(mqd_t mqdes, char *msg_ptr, size_t msg_len, unsigned *msg_prio);
```

- `mqdes` is the queue descriptor,
- `msg_ptr` is a pointer to the message buffer (for sending) or the buffer to be filled (for receiving),
- `msg_len` is the size of the `msg_ptr` buffer in bytes (must not exceed `mq_msgsize` when sending; must be ≥ `mq_msgsize` when receiving),
- `msg_prio`:
  - for `mq_send`, this is the message’s priority (must be less than `MQ_PRIO_MAX` — POSIX guarantees `MQ_PRIO_MAX >= 32`),
  - for `mq_receive`, it is a pointer to a variable where the message priority will be stored (can be `NULL` if the priority is not needed).

If you try to read from an empty queue or write to a full queue in non-blocking mode, the functions return -1 and set `errno` to `EAGAIN`.

In blocking mode, the functions will wait until the operation becomes possible.

If `mq_send` succeeds, it returns 0.

`mq_receive` returns the size (in bytes) of the received message.

In blocking mode, we can also set a maximum wait time for a message or for sending it. For this, use `mq_timedsend` and `mq_timedreceive`:

```c
int mq_timedsend(mqd_t mqdes, const char *msg_ptr, size_t msg_len, unsigned msg_prio, const struct timespec *abstime);
ssize_t mq_timedreceive(mqd_t mqdes, char *restrict msg_ptr, size_t msg_len, unsigned *restrict msg_prio, const struct timespec *restrict abstime);
```

These functions add the `abstime` argument, a pointer to a `timespec` struct (from `<time.h>`), which defines an absolute timeout after which the function will stop waiting (to receive a message or to send one).

They behave like their non-timed counterparts, except that if the timeout is exceeded, they return -1 and set `errno` to `ETIMEDOUT`.

IMPORTANT: As mentioned, `abstime` is an absolute timeout. To use it correctly, you must first retrieve the current time using, for example, `clock_gettime` with `CLOCK_REALTIME` (`man 3p clock_getres`), then add the desired wait time (e.g., add 1 to `tv_sec` for a 1-second wait).

When the queue is in non-blocking mode, `mq_timed(send|receive)` behaves exactly the same as `mq_(send|receive)`.

### Notifications

POSIX provides the ability to asynchronously notify processes about incoming messages to an empty queue.

To register a process for notification, use the `mq_notify` function (`man 3p mq_notify`):

```c
int mq_notify(mqd_t mqdes, const struct sigevent *notification);
```

- `mqdes` is the descriptor of the open queue,
- `notification` is a pointer to a `sigevent` structure (header `<signal.h>`) that specifies how the notification should be delivered.

The `sigevent` structure should be filled out depending on the notification type (`man 7 sigevent`):

For signal-based notification (only realtime signals):

- set `sigev_notify` to `SIGEV_SIGNAL`,
- set `sigev_signo` to the signal you want to receive (e.g., `SIGRTMIN`),
- set `sigev_value.sival_int` or `sigev_value.sival_ptr` to the value you want to receive in the signal handler argument (an integer or a memory address, respectively).

Additionally:

- when setting the signal handler using the `sigaction` function, the `sigaction` structure passed to the function must have the `sa_flags` field set to `SA_SIGINFO` (see the `sethandler` function from the solution in Task 1),
- the values passed in `sigev_value` are delivered to the handler in the `si_value` field of the `siginfo_t` structure (see the `mq_handler` function in the task solution).

For thread-based notification:

- set `sigev_notify` to `SIGEV_THREAD`,
- set `sigev_notify_function` to a pointer to a function that takes a `union sigval` (the type of `sigev_value`) and returns `void`,
- set `sigev_value.sival_int` or `sigev_value.sival_ptr` to the value you want to pass to the above function (integer or memory address),
- optionally set thread parameters in `sigev_notify_attributes`.

To unregister a process from notifications, call `mq_notify` with `notification` set to `NULL`.

Passing `NULL` when no process is registered will return -1 and set `errno` to `EINVAL`.

IMPORTANT:

- Notifications are one-time only: after a notification is delivered, no further notifications are expected. To receive more, you must call `mq_notify` again.
- Notifications are only triggered when the queue transitions from empty to non-empty.
- Only one process can be registered for notification. Otherwise, `mq_notify` returns -1 and sets `errno` to `EBUSY`.

Refer to the signal-based notification implementation in Task 1.

Thread-based notification is demonstrated in the solution for Task 2.

## Notes

- You must link the `librt` library when compiling programs that use POSIX message queues.
- If you open an existing queue, it may already contain data. You should not assume it is empty. To ensure a clean state, delete the queue before recreating it.

## Tasks with Solutions

### Task 1: Signal-Based Notification

Write a program that simulates a simple version of bingo. The parent process randomly draws numbers, and the players are its child processes. Communication between them takes place via POSIX message queues.

The parent process creates n child processes (0 < n < 100, where n is a program argument) and two message queues.

- The first queue, `pout`, is used to send randomly drawn numbers from the range [0,9] to the children once per second.
- The second queue, `pin`, is used to receive messages from the children when they win or complete the game.

Each child process randomly selects its winning number E (in [0,9]) and a number N representing how many numbers it will read from the queue (also from [0,9]). Then, in a loop, the child tries to read numbers from the `pout` queue — a sent number can only be received by one process, not all of them simultaneously.

Each child compares the received number with its E. If they match, the child sends this number to the parent via the `pin` queue and exits.

If the child reads N numbers without a match, it sends its own process number (from [1, n]) to the parent via `pin` before exiting.

The parent process must asynchronously receive messages from the `pin` queue and print the appropriate output, while still sending numbers every second.

When all child processes terminate, the parent also ends execution and removes both queues.

NOTE: For this task, message size in the queue should be limited to 1 byte!

#### Task Solution

New manpages:

- `man 7 mq_overview`
- `man 3p mq_open`
- `man 3p mq_close`
- `man 3p mq_unlink`
- `man 3p mq_getattr`
- `man 3p mq_setattr`
- `man 3p mq_send`
- `man 3p mq_receive`
- `man 3p mq_notify`
- `man 7 sigevent`

```c
#define _GNU_SOURCE
#include <errno.h>
#include <mqueue.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define LIFE_SPAN 10
#define MAX_NUM 10

#define ERR(source) \
    (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source), kill(0, SIGKILL), exit(EXIT_FAILURE))

volatile sig_atomic_t children_left = 0;

void sethandler(void (*f)(int, siginfo_t *, void *), int sigNo)
{
    struct sigaction act;
    memset(&act, 0, sizeof(struct sigaction));
    act.sa_sigaction = f;
    act.sa_flags = SA_SIGINFO;
    if (-1 == sigaction(sigNo, &act, NULL))
        ERR("sigaction");
}

void mq_handler(int sig, siginfo_t *info, void *p)
{
    mqd_t *pin;
    uint8_t ni;
    unsigned msg_prio;

    pin = (mqd_t *)info->si_value.sival_ptr;

    static struct sigevent notif;
    notif.sigev_notify = SIGEV_SIGNAL;
    notif.sigev_signo = SIGRTMIN;
    notif.sigev_value.sival_ptr = pin;
    if (mq_notify(*pin, &notif) < 0)
        ERR("mq_notify");

    for (;;)
    {
        if (mq_receive(*pin, (char *)&ni, 1, &msg_prio) < 1)
        {
            if (errno == EAGAIN)
                break;
            else
                ERR("mq_receive");
        }
        if (0 == msg_prio)
            printf("MQ: got timeout from %d.\n", ni);
        else
            printf("MQ: %d is a bingo number!\n", ni);
    }
}

void sigchld_handler(int sig, siginfo_t *s, void *p)
{
    pid_t pid;
    for (;;)
    {
        pid = waitpid(0, NULL, WNOHANG);
        if (pid == 0)
            return;
        if (pid <= 0)
        {
            if (errno == ECHILD)
                return;
            ERR("waitpid");
        }
        children_left--;
    }
}

void child_work(int n, mqd_t pin, mqd_t pout)
{
    srand(getpid());
    uint8_t my_bingo = (uint8_t)(rand() % MAX_NUM);
    uint8_t ni;
    for (int life = rand() % LIFE_SPAN + 1; life > 0; life--)
    {
        if (TEMP_FAILURE_RETRY(mq_receive(pout, (char *)&ni, 1, NULL)) < 1)
            ERR("mq_receive");
        printf("[%d] Received %d\n", getpid(), ni);
        if (my_bingo == ni)
        {
            if (TEMP_FAILURE_RETRY(mq_send(pin, (const char *)&my_bingo, 1, 1)))
                ERR("mq_send");
            return;
        }
    }
    if (TEMP_FAILURE_RETRY(mq_send(pin, (const char *)&n, 1, 0)))
        ERR("mq_send");
}

void parent_work(mqd_t pout)
{
    srand(getpid());
    while (children_left)
    {
        uint8_t ni = (uint8_t)(rand() % MAX_NUM);
        if (TEMP_FAILURE_RETRY(mq_send(pout, (const char *)&ni, 1, 0)))
            ERR("mq_send");
        sleep(1);
    }
    printf("[PARENT] Terminates \n");
}

void create_children(int n, mqd_t pin, mqd_t pout)
{
    while (n > 0)
    {
        switch (fork())
        {
            case 0:
                child_work(n, pin, pout);
                exit(EXIT_SUCCESS);
            case -1:
                ERR("fork");
        }
        children_left++;
        n--;
    }
}

void usage(char *name)
{
    fprintf(stderr, "USAGE: %s n k p l\n", name);
    fprintf(stderr, "100 > n > 0 - number of children\n");
    exit(EXIT_FAILURE);
}

int main(int argc, char **argv)
{
    int n;
    if (argc != 2)
        usage(argv[0]);
    n = atoi(argv[1]);
    if (n <= 0 || n >= 100)
        usage(argv[0]);

    mqd_t pin, pout;
    struct mq_attr attr = {};
    attr.mq_maxmsg = 10;
    attr.mq_msgsize = 1;
    if ((pin = TEMP_FAILURE_RETRY(mq_open("/bingo_in", O_RDWR | O_NONBLOCK | O_CREAT, 0600, &attr))) == (mqd_t)-1)
        ERR("mq_open in");
    if ((pout = TEMP_FAILURE_RETRY(mq_open("/bingo_out", O_RDWR | O_CREAT, 0600, &attr))) == (mqd_t)-1)
        ERR("mq_open out");

    sethandler(sigchld_handler, SIGCHLD);
    sethandler(mq_handler, SIGRTMIN);
    create_children(n, pin, pout);

    static struct sigevent noti;
    noti.sigev_notify = SIGEV_SIGNAL;
    noti.sigev_signo = SIGRTMIN;
    noti.sigev_value.sival_ptr = &pin;
    if (mq_notify(pin, &noti) < 0)
        ERR("mq_notify");

    parent_work(pout);

    mq_close(pin);
    mq_close(pout);
    if (mq_unlink("/bingo_in"))
        ERR("mq unlink");
    if (mq_unlink("/bingo_out"))
        ERR("mq unlink");
    return EXIT_SUCCESS;
}
```

#### Notes and Questions

Pay attention to the use of the pointer sent with the signal. The signal handler function prototype includes an additional `siginfo_t*` parameter, and the `SA_SIGINFO` flag is used when installing the handler to enable pointer passing. Note that we are not sending this signal manually — we receive it as a notification from the queue. The `kill` function cannot send a pointer; this can only be done using `sigqueue`.

Numbers are passed using the `uint8_t` type (`stdint.h`), which is a one-byte unsigned integer ranging from 0 to 255. Fixed-size integer types (e.g., `int32_t`) are more portable than base types like `int`, which can vary in size across platforms.

Since the program involves signal handling, protection from signal interruptions is required, e.g., using `TEMP_FAILURE_RETRY`. These macros were added throughout the code, although only the parent process’s code is at risk of interruption, as it is the only one receiving notifications from the queue. Adding such safeguards does not degrade performance and makes the code more portable.

> **Question:** One of the parent process’s calls lacks signal interruption protection — which one, and why is it not necessary there?
>
> **Answer:** The `mq_receive` call inside the signal handler function. We don’t expect the handler itself to be interrupted by the signal it’s handling, because that signal is blocked during its own handling by default.

> **Question:** How are child processes counted?
>
> **Answer:** By counting successful `waitpid` calls in the `SIGCHLD` handler. Signals like `SIGCHLD` can coalesce, so we do not count the signals themselves. The counter is stored in a global variable.

> **Question:** Why do we install/restart the notification before reading from the queue?
>
> **Answer:** If we read the queue first and install the notification afterward, a message could arrive in the queue in between — and because notifications are triggered only when a message appears in an empty queue, we would miss it. Installing the notification first guarantees that the queue is empty and a new message will generate a notification.

> **Question:** Why is one of the queues set to non-blocking mode?
>
> **Answer:** The `pin` queue is non-blocking due to the above reason. If it blocked, the program could hang inside the asynchronous signal handler after reading the last message, which would be a serious error.

> **Question:** How are message priorities used, and how does that relate to the 1-byte message size limit?
>
> **Answer:** Priorities are used not for ordering but to indicate the type of message. Because we’re limited to 1-byte messages, it’s hard to encode anything beyond a single number. Whether it’s a winning message or a game-over notice is indicated via the priority.

A significant part of the program logic is implemented inside the signal handler, which is acceptable because there’s no dependency between the number-drawing code and the notification-handling code. However, to make it more challenging, try moving all message-handling logic into the main parent process code (i.e., outside the asynchronous signal handler).

### Task 2: Thread-based Notification

Write a program simulating conversations on a Roman forum.

- Define a constant `CHILD_COUNT`.
- The parent process creates `CHILD_COUNT` queues, opens them in non-blocking mode, and spawns `CHILD_COUNT` child processes.
- Each child receives a randomly generated name.
- Each child acts as a citizen on the forum.
- Citizens randomly send each other messages containing their names, and upon receiving messages, they print them prefixed with their own name.
- After each message is sent, they sleep for a random amount of time.
- After sending `ROUNDS` messages, they exit.
- Each citizen waits for messages using thread-based notification.

#### Solution

```c
#include <errno.h>
#include <fcntl.h>
#include <mqueue.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

#define CHILD_COUNT 4

#define QUEUE_NAME_MAX_LEN 32
#define CHILD_NAME_MAX_LEN 32

#define MSG_SIZE 64
#define MAX_MSG_COUNT 4

#define ROUNDS 5

#define ERR(source) \
    (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source), kill(0, SIGKILL), exit(EXIT_FAILURE))

mqd_t create_queue(char* name)
{
    struct mq_attr attr = {};
    attr.mq_maxmsg = MAX_MSG_COUNT;
    attr.mq_msgsize = MSG_SIZE;

    mqd_t res = mq_open(name, O_RDWR | O_NONBLOCK | O_CREAT, 0600, &attr);
    if (res == -1)
        ERR("mq_open");

    return res;
}

typedef struct
{
    char* name;
    mqd_t queue;
} ChildData;

void handle_messages(union sigval data);

void register_notification(ChildData* data)
{
    struct sigevent notification = {};
    notification.sigev_value.sival_ptr = data;
    notification.sigev_notify = SIGEV_THREAD;
    notification.sigev_notify_function = handle_messages;

    int res = mq_notify(data->queue, &notification);
    if (res == -1)
        ERR("mq_notify");
}

void handle_messages(union sigval data)
{
    ChildData* child_data = data.sival_ptr;
    char message[MSG_SIZE];

    register_notification(child_data);

    for (;;)
    {
        int res = mq_receive(child_data->queue, message, MSG_SIZE, NULL);
        if (res != -1)
            printf("%s: Accepi \"%s\"\n", child_data->name, message);
        else
        {
            if (errno == EAGAIN)
                break;
            else
                ERR("mq_receive");
        }
    }
}

void close_queues(mqd_t* queues)
{
    for (int i = 0; i < CHILD_COUNT; ++i)
    {
        mq_close(queues[i]);
    }
}

void unlink_queues(char queue_names[CHILD_COUNT][CHILD_NAME_MAX_LEN])
{
    for (int i = 0; i < CHILD_COUNT; ++i)
    {
        int result = mq_unlink(queue_names[i]);
        // The case when the queue does not exist already
        // is not treated as an error
        if (result == -1 && errno != ENOENT)
            ERR("mq_close");
    }
}

void send_message(mqd_t queue, char* content)
{
    int result = mq_send(queue, content, MSG_SIZE, 0);
    if (result == -1)
        ERR("mq_send");
}

void child_function(char* name, mqd_t* queues, int i)
{
    printf("%s: A PID %d incipiens.\n", name, getpid());
    srand(getpid());

    ChildData child_data = {};
    child_data.name = name;
    child_data.queue = queues[i];

    union sigval data;
    data.sival_ptr = &child_data;
    handle_messages(data);

    for (int i = 0; i < ROUNDS; ++i)
    {
        int receiver = rand() % CHILD_COUNT;
        char message[MSG_SIZE];
        switch (rand() % 3)
        {
            case 0:
                snprintf(message, MSG_SIZE, "%s: Salve %d!", name, receiver);
                break;
            case 1:
                snprintf(message, MSG_SIZE, "%s: Visne garum emere, %d?", name, receiver);
                break;
            case 2:
                snprintf(message, MSG_SIZE, "%s: Fuistine hodie in thermis, %d?", name, receiver);
                break;
        }

        send_message(queues[receiver], message);

        int sleep_time = rand() % 3 + 1;
        sleep(sleep_time);
    }

    printf("%s: Disceo.\n", name);

    exit(EXIT_SUCCESS);
}

void spawn_child(char* name, mqd_t* queues, int i)
{
    switch (fork())
    {
        case 0:
            child_function(name, queues, i);
        case -1:
            ERR("fork");
    }
}

int main(void)
{
    mqd_t queues[CHILD_COUNT];
    char names[CHILD_COUNT][CHILD_NAME_MAX_LEN];
    char queue_names[CHILD_COUNT][CHILD_NAME_MAX_LEN];

    for (int i = 0; i < CHILD_COUNT; ++i)
    {
        snprintf(queue_names[i], QUEUE_NAME_MAX_LEN, "/child_%d", i);
        queues[i] = create_queue(queue_names[i]);

        snprintf(names[i], CHILD_NAME_MAX_LEN, "Persona %d", i);
    }

    for (int i = 0; i < CHILD_COUNT; ++i)
    {
        spawn_child(names[i], queues, i);
    }

    close_queues(queues);

    while (wait(NULL) > 0)
        ;

    printf("Parens: Disceo.");

    unlink_queues(queue_names);

    return EXIT_SUCCESS;
}
```

#### Notes and Questions

> **Question:** Why do we break the `mq_receive` loop on `EAGAIN`?
>
> **Answer:** This error means the queue is empty and there’s nothing more to read.

> **Question:** Why does `child_function` call `handle_messages` and not just `register_notification`?
>
> **Answer:** Because if messages are already in the queue from other children, no notification will be triggered. We must read those messages in the main thread.

> **Question:** The parent process closes all queue descriptors immediately after creating the children. Why doesn’t this cause problems for the children?
>
> **Answer:** Because children inherit a copy of the parent’s data, including file descriptors. Closing them in the parent does not affect the children’s copies.

> **Question:** Why don’t the child processes close the queues at the end?
>
> **Answer:** Closing a queue removes its notification, meaning no new handler threads will start. However, if a thread is already running while the queue is closed, it may attempt `mq_notify` or `mq_receive` on an invalid descriptor. Therefore, queues must remain open until the program ends. The OS will close them when the program exits, so it’s not an error.

> **Question:** Could we just wait for the notification handler thread to finish before closing the queues?
>
> **Answer:** No. We don’t have the thread’s TID. Even if it were shared, we wouldn’t know if the thread still exists when closing queues. Also, the thread might be in detached mode — such threads can’t be joined.

> **Question:** Could we use a synchronization structure to prevent this issue?
>
> **Answer:** Unfortunately, no. If we used one, we’d need to destroy it at the end of the program. But the thread might still be running and try to access the destroyed structure. In this case, there’s no perfect solution. Since closing the queue means the program is ending anyway, if threads were writing to a file, we could use a condition variable to ensure they finish — but in this case, it’s unnecessary.

> **Question:** Can we move the `exit(EXIT_SUCCESS)` call from `child_function` to `spawn_child`, right after calling `child_function`?
>
> **Answer:** No, for the same reason we don’t close queues. The `child_data` would be out of scope after `child_function`, but it’s still needed by the handler thread. Leaving `exit(EXIT_SUCCESS)` inside `child_function` ensures it stays valid.

## Example Exercises

Complete the sample exercises. You will have more time and starter code during the lab session, but completing the tasks below on your own means you are well prepared.
