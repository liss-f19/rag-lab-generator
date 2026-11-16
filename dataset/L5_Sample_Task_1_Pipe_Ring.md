# L5 Sample Task 1: Pipe Ring

*Topic: L5 — FIFO/pipe (sample task)*


## Goal

Write a program that uses pipes to communication between three processes. The first process (parent) is connected using pipe to second process, which is connected to third process. The third process is connected back to the parent process, so all processes exchange messages in ring topology.

After creating processes and pipes parent process sends 1 (as a null-terminated string). After that each process after receiving new number prints it to terminal with its PID. Then it add to that number random value in range [-10,10] and sends to the next process. If one of process receives 0 it should terminate. Other process should detect broken pipe and also terminates. All resources (memory, pipes) should be correctly released.

## Stages

### Stage 1

Create processes and pipes, correctly close unused descriptors. Each process should print descriptor it uses and closes. Parent process wait for children and then terminates.

### Stage 2

Each process sends random number in range [0-99] and prints number received with its PID to stdout. At this stage you should handle variable length messages.

### Stage 3

Parent process sends 1, which travels without any change until receiving C-c.

### Stage 4

Add number changing, STOP condition and pipe break check.
