# L7: Dog Races

*Topic: L7 — Shared memory and mmap*


The year is 2137. The cities lie silent beneath layers of ivy and rubble — relics of a forgotten age when humans ruled the Earth. In their place, a new order reigns: canine civilization. What was once a quiet bark in the distance is now the roar of a global government shaped entirely by dogs. They roam the once-human cities freely, paws firm on the concrete of abandoned malls, tails wagging beneath crumbling billboards. Gone are the days of cats on the internet and people walking Labradors in parks. Now, Labradors walk each other. They've built societies, developed institutions, and — in a feat no one predicted — reinvented sports entirely.

Among all canine competitions, one stands above the rest: the Great Track Race. Fast, chaotic, and relentlessly fair, it's a raw test of speed, direction, and instinct. Thousands gather to watch across bark-cast networks, as carefully trained racers line up at the starting line. The track: a long stretch of open pavement, repurposed from forgotten highway lanes. The rules: simple. Go forward. Turn around. Come back. Avoid collisions. Win. And above all: do not bite the competition.

But in a world ruled by tails and teeth, glory must be recorded — and so, the leaderboard was born. It holds the names (or rather, process IDs) of champions. A testimony to those who sprinted fastest, dodged collisions, barked at danger, and made it to the end first.

**The simulation must be implemented using shared memory and processes.**

## Stages

### Stage 1 (5 p.)

The program accepts two parameters: 16 ≤ *L* ≤ 256 – racetrack length, and 2 ≤ *N* ≤ 6 – number of dog processes.

- Create a shared anonymous memory region to store all shared variables, including synchronization primitives (barriers, mutexes, etc.).
- Create *N* dog processes. Each dog process waits at a barrier for the race to begin.
- Each process must initialize its random number generator using a unique seed (e.g., its PID).
- Once all *N* dogs arrive at the barrier, the barrier releases, and each process prints:

  ```
  [PID] waf waf (started race)
  ```

- After printing this message, each process proceeds to its race logic (to be implemented in the next stage).
- The main process waits for all dog processes to complete before exiting.

### Stage 2 (8 p.)

The racetrack is represented as a one-dimensional array of length *L*. Each element represents one track segment that may hold at most one dog, identified by its PID.

Each dog process starts outside the track (at position -1) and repeatedly performs the following steps until it reaches the end of the track:

1. Wait for a random time in the range [250, 1250] milliseconds.
2. Generate a random integer in the range [1, 6] to determine the movement distance.
3. Attempt to move according to the generated distance and current direction (initially forwards). If the target index exceeds the racetrack bounds, move as far as possible, then switch direction.
4. If the destination cell is already occupied (i.e., not zero), print:

   ```
   [PID] waf waf (the field is occupied)
   ```

   and remain in current position.
5. Otherwise, perform the move:
   - (a) Print the new position:

     ```
     [PID] waf waf (new position = [POSITION])
     ```

   - (b) Update:
     - The old position (reset to 0/empty)
     - The new position (set to PID)

Once a dog reaches the end of the track, it prints:

```
[PID] waf waf (finished race)
```

Access to each array element must be protected by a separate mutex assigned per track segment.

### Stage 3 (6 p.)

Create an additional commentator process. It prints the entire state of the racetrack every 1 second in the following format:

```
--- --- 303426> <303429 --- --- --- 303428> <303430 <303431
```

In the track printout:

- Empty cells are represented by `---`
- Cells with dogs show `[PID]>` for dogs moving forward and `<[PID]` for those moving backward

The commentator continues printing until all dogs have finished the race. This is tracked via a shared counter, initially 0, which is incremented (under a mutex) each time a dog completes the race.

The printing of the entire track state must be atomic.

**Hint:** You may use `rwlock` to guarantee atomicity of the operation.

- All racetrack updates (by dogs) acquire a read lock from an `rwlock`
- The commentator acquires a write lock before reading the entire racetrack

### Stage 4 (6 p.)

Map a file named `leaderboard` into the processes' memory.

Each time a dog reaches the end of the racetrack, it writes its result to the file in the format:

```
[PLACEMENT]. Dog [PID]
```

For example:

```
1. Dog 303426
2. Dog 303427
...
```

- Each entry might be of fixed length, padded with spaces.
- Each entry starts on a new line.
- Dogs must synchronize access to the file using a mutex to prevent race conditions.
- After writing an entry, the corresponding data must be synchronized to disk immediately.
- The use of streams and the `write` function is forbidden.
