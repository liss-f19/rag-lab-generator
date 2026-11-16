# L3: Potosí Mines


Deep in the Andes Mountains of South America lies the fabled Cerro Rico, the "Rich Mountain," near the mining settlement of Potosí. The Spanish Empire, desperate to fund its vast colonial ambitions, has decreed an enormous undertaking: to locate and extract every ounce of mineral wealth hidden deep within the mountainous labyrinth.

For decades, human laborers have dug chaotically, exhausting surface deposits with little to show for their efforts. The mine's tunnels, carved over generations, have grown into an incomprehensible maze. To put an end to this inefficiency, Spanish engineers have devised a revolutionary system to bring order to the chaos. They've mapped the entire mine into a directory tree, where each shaft, cavern, and tunnel corresponds to a folder or subfolder. Every file in this tree represents a specific excavation site, marked for further extraction.

To replace the grueling manual labor of humans, the Empire has introduced a groundbreaking fleet of steam-driven excavators, mechanical marvels powered by pistons and gears, built explicitly for the task of mining and sorting ore. Each excavator is assigned to a portion of the mountain and operates in parallel across different sections of the mine.

Excavation sites are represented as files within the directory tree. These files contain raw materials encoded as bytes, representing what was unearthed from each site:

- Bytes with values `'0'`–`'9'` represent precious minerals and gemstones.
- All other byte values are plain rock or debris, to be discarded.

Your mission is to design the software that will control these mechanical excavators. Each excavator will traverse through the shafts (folders) and locate its excavation site (file), then excavate the contents of the file into shared repository (an array).

This ambitious operation promises to restore the Empire's dwindling treasure by harnessing an unprecedented mix of engineering and efficient excavation methods.

**It is not permitted to use global or static variables. Only low-level APIs (`read`, `close`, `readdir`, etc.) may be used for reading files.**

## Stages

### Stage 1 (6 p.)

Write a program that scans a directory given as a parameter *p* using threads. Create a thread that scans the *p* directory. Print each encountered entry (both files and directories) in the following format: `"THREAD_ID: ENTRY_PATH"`. Wait for the scanning thread to finish.

### Stage 2 (6 p.)

Make the scanning thread recursive. When the scanning thread encounters a directory create a new thread that recursively scans that directory. Wait for all created threads to finish.

### Stage 3 (6 p.)

When any scanning thread encounters a file it will create a new thread that will read the file and count quantity of numeric characters (`'0'` - `'9'`) in the file. Create an array to store the quantities of each character shared between all threads. Protect access to each counter with dedicated mutex. Read in batches of 10. Move the results from the buffer into the shared array and sleep 1 millisecond between each read from the file. After all threads have finished print the counters.

### Stage 4 (6 p.)

Add a signal handling thread. It will handle 2 signals. When a `SIGUSR1` arrives print partial counters (the whole array needs to be locked when printing). On a `SIGINT` immediately stop the operation of all threads. Wait for the signal handling thread to finish as well.
