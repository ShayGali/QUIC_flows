# QUIC flows

This is the final project for the course "Communication Networks."

The project instructions can be found [here](./final_project.pdf).

An explanation of the project and the 'dry part' of the assignment can be found [here](./explanation.pdf).

### Requirements

- Python 3.12

### Running the project

1. Clone the repository
2. Run the following command:

```bash
py receiver.py
py sender.py <file_name> <number of streams>
```

you can use this command as well:

* not send a file:
  the default file is [inputs/1mb_file.txt](./inputs/1mb_file.txt)

```bash
py sender.py <number of streams>
```

* not send a file and not specify the number of streams:
  the default number of streams is 1, and the default file is [inputs/1mb_file.txt](./inputs/1mb_file.txt)

```bash
py sender.py
```

### Collaborators

- [Hagay Cohen](https://github.com/hagaycohen2)
- [Chanan Helman](https://github.com/chanan-hash)
- [Oz Atar](https://github.com/LILOZI)