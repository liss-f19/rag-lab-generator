# RL2: Carramba!

*Topic: RL2 — Retake lab*


*A long, long time ago, a famous researcher of flying frogs – Professor Baltazar Gąbka – went missing in the Land of Raindwellers. An expedition sets out from Kraków to rescue him, led by the no less famous traveller – Wawel Dragon (buhuhahaha!) – who is accompanied on their perilous expedition by the princely cook Bartholomew Bartolini of Green Parsley coat of arms (mamma mia! at your service!). They are followed by the mysterious Don Pedro...*

*...a spy from the Land of Raindwellers.*¹

The citizens of Kraków know very well that the Raindwellers are very unhappy after Professor's visit and they are not going after the Dragon. They are going after them and the expedition is just standing in their way. Therefore, they want a live preview of the state of the rescue expedition to prepare in case of danger and ensure the success of the expedition. However, a clever spy has anticipated the fears of the inhabitants of Prince Krak's city and, following Wawel Dragon and Bartholomew Bartolini, obliterates their tracks so that they are not visible from afar.

With little confidence in the students of the Jagiellonian University, the citizens of Kraków plan to ask a technical university to write an app for tracking the expedition. The choice fell on WUT, and it was you, the master of your trade, who were appointed to carry out the task. Help the people of Kraków secure the success of the expedition!

The file `board_utils.h` contains helper functions (along with their descriptions) used to initialise the board and perform the character movements. Make use of these functions in your code.

## Stages

### Stage 1 (5 p.)

The program takes two integers greater than 2 as arguments: *n* and *m*. Create a file named `BOARD_FILE` of size *m* × (*n* + 1) bytes, and map its contents to a shared memory area. Then, initialise the mapped memory using the provided function `fill_board` (from the file `board_utils.h`).

After initialisation, in a loop make `STEP_COUNT` random expedition moves (get the move using the function `get_random_move` and perform it with `move_pos`), starting from a random position. Mark the position of the expedition (using `set_char`) with `S` and the trace after it with `=`. Sleep 100ms after each movement.

At the end, print `Smok-Expedition completed!`, release all resources and exit the program. You can view the contents of the created file to ensure that the memory has been filled correctly. To follow the changes real-time in the file, use `watch -n 0.1 tail board` while the program is running.

### Stage 2 (5 p.)

Create a Don Pedro's process that will be used to keep track of the expedition. At this stage, the map becomes a critical section – secure access to it with a single **shared mutex**.

Don Pedro first sleeps `WAIT_N*100` ms and then makes `STEP_COUNT` movements (in a loop), tracking the expedition (parent process). To accomplish this:

- if Don Pedro is on the track of Dragon (`has_trail` returns non-zero value), then change the content of the field where Don Pedro stays currently to a space (`' '`); otherwise, change the content of this field to a dot (`'.'`) and print `Carramba!` to the terminal,
- fetch the move to be executed using the function `get_trail_move` and perform it (`move_pos`).

### Stage 3 (5 p.)

The expedition realises that it is being followed. Dragon therefore comes up with the idea of sending false signals to the spy about the direction the expedition would go. To do this, create (and open for writing) in the parent process a FIFO file named `FIFO_NAME` and open it for reading in the spy's process.

*[Продолжение этапа 3 и этапы 4 (6 p.) и 5 (4 p.) на фото отсутствуют — следующая страница не сфотографирована.]*

---

¹ This is a quote from a Polish animated series „Porwanie Baltazara Gąbki". You are strongly engouraged to watch after the labs!
