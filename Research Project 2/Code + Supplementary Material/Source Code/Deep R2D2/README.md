# Usage Instructions

To make use of this file, replace it with the existing file located at: https://github.com/michaelnny/deep_rl_zoo/blob/main/deep_rl_zoo/networks/dqn.py.
This will modify the existing model architecture to match the deeper variant as detailed in the paper.
Or use the deep_rl_zoo-main file provided in the Deep R2D2 folder (this has the dqn.py file already replaced).

## Installation

Upon replacing the file, instructions on installing relevant requirements can be found in the documentation of the Deep RL Zoo repository.

## Commands

The following commands will allow you to run the agent, choosing the number of actors, batch size, environment name, etc.

```bash
python3 -m deep_rl_zoo.r2d2.run_atari environment_name=Breakout --num_actors=6

```

By default, the number of actors is set to 16 with a batch size of 4. Also the environment_name is set to Pong.
