# Summary: SOP2 lab 5 - FIFO/pipe

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP2 lab 5 - FIFO/pipe

Source: https://sop.mini.pw.edu.pl/en/sop2/lab/l5/

- Lab id: `sop2/l5`
- Tutorial sections: 12
- Tasks: 5
- Source files: 5

## Topics

`fifo`, `pipe`, `mkfifo`, `isalpha`, `exit`, `child_work`, `TEMP_FAILURE_RETRY`, `perror`, `fprintf`, `usage`, `read_from_fifo`, `read`, `isalnum`, `printf`, `open`, `close`, `write_to_fifo`, `getpid`, `memset`, `write`, `unlink`, `kill`, `sethandler`, `sigaction`, `sigchld_handler`, `waitpid`, `srand`, `rand`, `parent_work`, `create_children_and_pipes`, `fork`, `free`, `atoi`, `malloc`, `sig_handler`, `sig_killme`

## Tutorial outline

- **Tutorial 5 - FIFO/pipe** - # Tutorial 5 - FIFO/pipe > Introduction notes: > - All materials from OPS1 are still obligatory! > - Quick look at this material will not suffice, you should compile and run all the programs, check how they work, read additional materials like man pages. As you read the material please do all the ex
  - **Questions** - ## Questions Do you need to divide the communication into PIPE_BUF parts in case of one to one connection i.e. one process writes and one reads? **Answer:** There is no need to do it, there is no competition over the link, no interference from other processeses. Can you open a pipe or FIFO to commun
  - **Task 1 - FIFO** - ## Task 1 - FIFO Goal: Write client server application, communication between clients and the server is based on single shared FIFO. The server reads data from the connection,removes all non-alphanumerical characters from this input and prints processed data on the standard output along with senders
    - **Stage 1** - ### Stage 1 - Prepare simplified server that will create FIFO and will read data from it. What comes out of the FIFO will be filtered (alphanumeric chars only) and printed on the screen. - Use command `cat` as the client. Solution **prog21a_s.c**: ```c #include <ctype.h> #include <errno.h> #include 
    - **Stage 2** - ### Stage 2 - Prepare complete client program, it reads files and sends it via FIFO in PIPE_BUF chunks. - All chunks sent must be of PIPE_BUF size, including the last one. - Each chunk sent must be tagged with PID nuber Solution: **prog21_c.c**: ```c #include <errno.h> #include <fcntl.h> #include <l
    - **Stage 3** - ### Stage 3 - Add chunking on the server side. - Add FIFO removal Solution **prog21b_s.c**: ```c #include <ctype.h> #include <errno.h> #include <fcntl.h> #include <limits.h> #include <stdio.h> #include <stdlib.h> #include <sys/stat.h> #include <sys/types.h> #include <unistd.h> #define ERR(source) (p
  - **Task 2 - pipe** - ## Task 2 - pipe Goal: Write n-process program where n child processes communicate with parent over one shared pipe R and parent communicates with children using n dedicated pipes P1,P2,...,Pn On C-c parent process chooses random pipe Pk (where k in [1,n]) and sends random [a-z] char to it. On the s
    - **Stage 1** - ### Stage 1 - Create n child processes. - Create pipes. - Close unused descriptors. - Initiate random numbers. - Parent process awaits data on pipe R and prints them on the stdout, it terminates after all data is processed. - Child process sends random char on R pipe and exits. Solution **prog22a.c*
- **Stage 2** - # Stage 2 - Add SIGINT handling. - Protect system function from interruption by the signal handling function (all the code). - Add missing code. Solution **prog22b.c**: ```c #define _GNU_SOURCE #include <errno.h> #include <limits.h> #include <stdio.h> #include <stdlib.h> #include <string.h> #include
  - **Source codes presented in this tutorial** - ## Source codes presented in this tutorial - [prog21_c.c](prog21_c.c) - [prog21a_s.c](prog21a_s.c) - [prog21b_s.c](prog21b_s.c) - [prog22a.c](prog22a.c) - [prog22b.c](prog22b.c)
  - **Example tasks** - ## Example tasks Do the example tasks. During the laboratory you will have more time and the starting code. However, if you finish the following tasks in the recommended time, you will know you're well prepared for the laboratory. - [Task 1](https://sop.mini.pw.edu.pl/en/sop2/lab/l5/example1/) ~60 m
  - **Additional materials** - ## Additional materials - <http://cs341.cs.illinois.edu/coursebook/Ipc#pipes> - <http://cs341.cs.illinois.edu/coursebook/Ipc#named-pipes>

## Tasks

- **example1: Task on pipe/FIFO** - 4 stages
  1. Create processes and pipes, correctly close unused descriptors. Each process should print descriptor it uses and closes. Parent process wait for children and then terminates.
  2. Each process sends random number in range `[0-99]` and prints number received with its `PID` to stdout. At this stage you should handle variable length messages.
  3. Parent process sends `1`, which travels without any change until receiving C-c.
  4. Add number changing, STOP condition and pipe break check.
- **example2: Task on pipe/FIFO** - 5 stages
  1. Correct program initialization, creation of the player processes and the required pipes.
  2. Every player process sends a random nonnegative integer `≤ M` to the server, for each the server process writes `Got number <X> from player <index>` to the terminal.
  3. Implementation of rounds - the server cyclically sends to the players announcements that a new round has started. Players respond with a random card.
  4. Full implementation of the game's rules, as above.
  5. After a round starts, each player has a 5% chance of "failure" (premature termination). The server process correctly responds to such situation.
- **example3: Task on pipe/FIFO** - 27 stages
  1. **Process Creation:**
  2. The main process (teacher) creates `n` child processes (students).
  3. Each student prints their process ID and exits.
  4. **Attendance Check:**
  5. Students communicate with the teacher through pipes.
  6. A shared pipe allows students to write to the teacher, while the teacher communicates with each student through individual pipes.
  7. The teacher takes attendance by sending `Teacher: Is [PID] here?` to each student and the standard output.
  8. Students respond with `Student [PID]: HERE` through both the shared pipe and standard output.
  9. After the attendance check, all processes exit.
  10. **Task Stages:**
  11. After the attendance check, students begin the task by following these steps for each stage:
  12. Generate a random integer `t` in the range `[100, 500]`.
  13. Wait `t` milliseconds.
  14. Generate a random integer `q` from `[1, 20]`, representing their attempt score.
  15. Compute their total attempt score as `k + q`.
  16. Send their process ID and attempt score to the teacher.
  17. The teacher compares the attempt score against the stage difficulty (`d`), which is calculated as the stage's base points plus a random integer from `[1, 20]`.
  18. If `k + q >= d`, the student succeeds; otherwise, they fail. The information is sent back to the student.
  19. The teacher prints one of the following messages:
  20. `Teacher: Student [PID] finished stage [X]` (on success).
  21. `Teacher: Student [PID] needs to fix stage [X]` (on failure).
  22. If a student completes all four stages, they print `Student [PID]: I NAILED IT!` and exit.
  23. The teacher waits for all students to finish. After all students exit, the teacher prints `Teacher: IT'S FINALLY OVER!` and exits.
  24. **Time Limit:**
  25. The laboratory session may end if time runs out. This is handled using the `alarm(2)` function after attendance is checked.
  26. When the `SIGALRM` signal is received, the teacher prints `Teacher: END OF TIME!`, stops grading students, and prints a summary table before releasing resources and exiting.
  27. Each student detects that the teacher has left and prints `Student [PID]: Oh no, I haven't finished stage [X]. I need more time.` before exiting.
- **example4: Task on pipe/FIFO** - 10 stages
  1. The dealer (main process) creates `N` player processes. Each player prints: `[process id]: I have [amount] and I'm going to play roulette`.
  2. Players communicate with the dealer via pipes. Each player sends a bet amount (within their balance) and a chosen number.
  3. The dealer prints: `Dealer: [process id] placed [amount] on [number]` after receiving a bet.
  4. The dealer draws a random number and announces: `Dealer: [number] is the lucky number`.
  5. After one round, all players and the dealer exit.
  6. The game continues as long as at least one player has money.
  7. If a player runs out of money, they print: `[process id]: I'm broke` and exit.
  8. If a player wins, they print: `[process id]: I won [amount]`.
  9. Once all players exit, the dealer prints: `Dealer: Casino always wins` and exits.
  10. Each round, a player has a 10% chance to leave with their remaining money. They print: `[process id]: I saved [amount left]` and exit.
- **example5: Task on pipe/FIFO** - 13 stages
  1. **Initialize:**
  2. The server process creates `N` player processes.
  3. It shuffles the deck and deals `M` cards to each player via pipes.
  4. Each player prints their received hand with their process ID and exits.
  5. **Gameplay:**
  6. Players form a ring, passing cards via pipes (`nᵗʰ` player → `(n+1 % N)ᵗʰ` player).
  7. A player who collects `M` cards of the same suit prints `[PID]: My ship sails!` (game runs endlessly).
  8. **Winning Condition:**
  9. The server creates a shared pipe for winners to announce victory.
  10. A player who wins writes their PID to the pipe, prints `[PID]: My ship sails!`, and exits.
  11. The server reads the PID, prints `Server: [PID] won!`, and exits.
  12. **Termination:**
  13. `Ctrl-C` instantly stops all processes and cleans up resources.

## Source files

- `src/prog21_c.c` (c)
- `src/prog21a_s.c` (c)
- `src/prog21b_s.c` (c)
- `src/prog22a.c` (c)
- `src/prog22b.c` (c)
