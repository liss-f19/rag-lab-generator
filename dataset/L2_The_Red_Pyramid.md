# L2: The Red Pyramid

*Topic: Processes, signals and descriptors*


It is the year 2573 B.C. The current pharaoh of Egypt is Hor-Nebmaat Snefru, the founder of the Fourth Dynasty of Egypt. After the massive failures that were the Meidum pyramid, and the Bent Pyramid of Dahshur, a new, third pyramid is being built, also at Dahshur.

Some say that the instability of the first two pyramids was caused by inadequate calculations performed by the builders. To avoid another failure, this time all stones used for the building the pyramid are going to be weighed before cutting. Because the reddish limestone used for building the pyramids has uniform density, it is enough to calculate the volume of each stone. Additionally, the program should simulate breaking up the stone into bricks.

To speed up the weighing process, accurate pictures of all the stones have been drawn by scribes on regular grids. Calculating the volume of each stone should be as easy as counting the number of filled in squares.

To facilitate this process, a new multiprocessor computer was set up by in the server room of the Bent Pyramid. Your task is to write the software for calculating the volumes of the stones in parallel.

A starting program has been placed in the repository. The file `stones` contains example input. Your solution should be based on it. **Remember to always check for errors reported by system functions and to free up allocated resources like memory and open file descriptors.**

## Stages

### Stage 1 (4 p.)

The program accepts input parameters as described by the `usage` function in the starting code. Start *k* child processes. Check, if *k* is in the accepted range. Print the PID of the parent process. Each child process should print its index, i.e. the first child should print 0, the second one 1, etc. After printing, the child processes exit. The parent process waits for termination of all child processes, prints "All workers have gone home.", and then it itself ends.

### Stage 2 (7 p.)

Open the file saved at *p*. Use low-level API (`open`, `close`, etc.). The file contains at least 8 stones composed of `*` character. Each stone is exactly 8 lines long and is followed by an empty line. You can assume that a stone is composed of no more than 512 characters. Read the file so that the *i*-th child should have access to the *i*-th one stone.

When all child processes are started, send `SIGUSR1` to all of them. After receiving it, the child processes end.

Remember to properly handle `EINTR` returned by system functions (i.e. do not abort the program!).

### Stage 3 (7 p.)

After receiving `SIGUSR1`, each child begins to weigh the stone. To weigh the stone count the number of `*` characters in the stone. For each 18 `*` counted, save a 6 × 3 rectangle made of `*` and a new line to a file named `<p>-<i>`, where *i* is the number of the child process (see an example on the other side). The process sleeps 0.5 seconds between each saved rectangle. Correctly handle sleep interruption (i.e. the total time slept should always be 0.5 seconds). After finishing, the process ends.

### Stage 4 (6 p.)

Add correct handling of `SIGINT` in the parent process and in child processes. A child process after receiving `SIGINT` should close all descriptors, send `SIGINT` to the parent, and exit. The parent process sends `SIGINT` to the children and awaits their completion, then exits. Each time any process receives `SIGINT`, print this information on `STDOUT`. Do not do this in the signal handler!

---

