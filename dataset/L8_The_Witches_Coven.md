# L8: The Witches' Coven

*Topic: L8 — Sockets and epoll*


A witch needs a coven, no matter how powerful. The Old Crone knows that and needs to cast a spell, but doesn't know any other witches like her. They're all hiding, fearing persecutions. The Crone has a clever solution. Instead of holding hands in a circle, she can cast the whole spell online! In the year 1432 the witches don't use social media yet, but they have their own communication protocol over TCP. In order to cast a spell, there needs to be a circle. Normally, it would be made by holding hands. In this case however, it will be a circle of network connections.

We can imagine the whole coven on the face of a clock. The Crone is at the top of this circle – midnight. The *mother witch* sits to the left, at the eleventh hour. The *maiden witch* to the right, on the first hour. Every other witch lies below, connecting the *maiden* with the *mother* all the way around the face of the clock. The Crone verifies every *candidate*. At all time the last accepted witch is considered the *maiden*, the first – the *mother*. When only one has been accepted it's considered both the *mother* and the *maiden witch* of the circle.

Your task is to write a **single-threaded and single-process** program for creating a circle of TCP connections for the Crone. **All data transmitted over the network must be in network byte order.** You can use the provided `sop-witch` application for testing. For the sake of testing during this laboratory the programs could be called as follows:

```
./sop-crone <port 1>
./sop-witch <port 2> localhost <port 1>
./sop-witch <port 3> localhost <port 1>
...
./sop-witch <port x> localhost <port 1>
```

## Stages

### Stage 1 (8 p.)

Implement buffered input from a TCP socket while taking care of incoming connections. Accept one connection and receive 3 bytes from it. Remember that due to the properties of sockets they could be received over more than one read. If someone tries to connect when still receiving, accept and immediately close that connection. After the 3 bytes have been received, print `"The ritual has started!"` and exit. If the connection closes prematurely, print `"No! The ritual..."` and exit instead. Utilize the `epoll` function (alternatively, `select` or `poll`).

### Stage 2 (5 p.)

The program has to comply with the simple communication protocol: A message consists of a single byte header and a variably sized body. The header specifies the size of the body in bytes, thus it can be at most 255 bytes long, and with the header – 256 bytes long. The 3 bytes received in the last stage were actually a 1 byte header and a 2 byte body containing a port number in network order. Don't exit after receiving those bytes now. Connect to the same address you received the message from (which we will call the *maiden witch*), but with the port you now received. We will call this connection the *mother witch*.

### Stage 3 (5 p.)

Send one message whose body contains 4 zeroed bytes to the *maiden witch*. Start receiving messages from the *mother witch*. When you fully receive a 4-byte-body message, print it as an integer. When you receive a message longer than 6 bytes, print it as a string. Ignore all other messages. Make sure that you're still accepting and closing all new connections during that process, just like in stage 1. If one of the two connections closes, print `"The maiden/mother witch left the coven, we are hopeless"` respectively and exit.

*Tip: it's not guaranteed that all bytes will be written on the first try.*

### Stage 4 (7 p.)

After completely sending a message to the *maiden witch* don't close the next connection you accept - it will be a *candidate*. Receive from it the first 2-byte-body message again – a port number. This time, instead of connecting to it yourself, send a 6-byte-body message to the *maiden witch* containing the 4-byte address, and then the 2-byte port number. She will close her connection with you and connect with the *candidate* instead. Have the *candidate* now function as the *maiden witch*, replacing the last one. Every time a *maiden witch* is assigned – send a new message whose body consists of 4 zeroed bytes, same as from stage 3.

*Tip: remember about byte order (`man 3type sockaddr`)*

If a *candidate* closes, print `"Another young one lost to the shadows"` and don't close the next accepted connection – another *candidate*.

## A schema of how the application communicates over the network in one scenario

```
On receiving a new connection "candidate" from address A at port X:
Start rejecting all new connections.
Accept data from "candidate" in the form:
- [1 byte] 2
- [2 bytes] port Y
After receiving, if "mother" is not already connected:
    Connect to address A at port Y. (connection "mother")
Else:
    Send data to "maiden" in the form:
    - [1 byte] 6
    - [4 bytes] address A
    - [2 bytes] port Y
Afterwards, in both cases, relabel the "candidate" connection
to "maiden". Then, at the same time:
    Send data to "maiden" in the form:
    - [1 byte] 4
    - [4 bytes] 0
        - after sending, start accepting candidates again
    Accept data from "mother" in the form:
    - [1 byte] 4
    - [4 bytes] N
        - after receiving, print N as integer
    Accept data from "mother" in the form:
    - [1 byte] M (M > 6)
    - [M bytes] s
        - after receiving, print s as string
```
