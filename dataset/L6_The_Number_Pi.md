# L6: The number π

*Topic: L6 — POSIX Queues*


The goal of this task is calculation of the number π using a Monte Carlo method. **In each stage remember to correctly hadle all errors, including `EINTR`, and to free all unused resources.**

## Stages

### Stage 1 (4 p.)

Create two POSIX queues with `MAX_MSG_COUNT` max message count and names `PARENT_QUEUE_NAME` and `WORK_QUEUE_NAME`. The parent queue should be opened in non-blocking mode and have message size of 1 byte, the work queue should be opened in blocking mode and have message size two times that of `float`. Create `CHILD_COUNT` child processes. Each process prints `Exiting` together with its PID. The parent waits for all child processes to end, then unlinks the queues and exits.

### Stage 2 (8 p.)

The parent process generates `ROUNDS` random points from [−1, 1]² (use `rand_float` function). Each time it generates a point, it sends it to the work queue. The children close the parent queue and reopen it in blocking mode. Then, in an infinite loop they read a point from the work queue, sleep for `SLEEP_TIME` miliseconds, print the point's coordinates, check if it lies in the disc centered at (0, 0) with radius 1, and print the result.

### Stage 3 (8 p.)

The children send the result calculated in the last stage to the parent queue. The parent process sets up a signal notification for the parent queue. The handler registers a new notification, receives messages from the queue and with each message prints `pi approximation: PI`, where `PI` is 4*i*/*n*, where *n* is the total number of messages received and *i* is the number of messages informing that a point was lying in the disc. You should expect the value to approach π as more messages are received. **It is forbidden to use any global variables.**

### Stage 4 (5 p.)

After generating the points, the parent sets the work queue to non-blocking mode using `mq_setattr`. This will cause the queue to become non-blocking even in the children. If a child detects `EAGAIN` when receiving from the queue, break the loop.
