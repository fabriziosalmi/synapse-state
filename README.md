# Synapse

A decentralized, collaborative live stream powered by YouTube and GitHub.

> This project turns a YouTube channel into a real-time canvas showing a network of all active participants. The state of the network is managed transparently in a public GitHub repository.

### How it Works

Each participant runs a small application (a `synapse-node`) on their computer. This application:
1.  Launches a tiny web server with a webpage showing a visualization of the network.
2.  Uses a headless browser to capture this webpage.
3.  Streams the captured video to a YouTube Live broadcast.
4.  Synchronizes with a shared GitHub repository to know about other active nodes.

When a new node comes online, it registers itself in the GitHub repository. All other active nodes see this change, and their visualization updates automatically. The result is a single, shared, dynamic visualization streamed simultaneously by all participants.

---

### Quick Start

You can run your own `synapse-node` in just a few steps using Docker.

**Prerequisites:**
*   [Docker](https://www.docker.com/get-started) and Docker Compose
*   [Git](https://git-scm.com/downloads)
*   A YouTube Account

#### Step 1: Create the State Repository

Create a new, **public** GitHub repository. This repository will be used to store the shared state of the network. You can leave it empty.

#### Step 2: Get YouTube API Credentials

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2.  Create a new project if you don't have one.
3.  Create new credentials -> **OAuth client ID**.
4.  Select **Desktop app** as the application type.
5.  Download the JSON file and rename it to `client_secrets.json`. Place it in the same folder as this README.

#### Step 3: Configure and Run

1.  **Clone this repository** (the one containing the `synapse-node` code).
2.  **Create your configuration file.** Copy `config.env.example` to `config.env` and fill in the `SYNAPSE_GIT_REPO_URL` with the URL of the public GitHub repository you created in Step 1.
3.  **Run the application:**
    ```bash
    docker-compose up --build
    ```

### What to Expect

The first time you run the command, a browser window will open, asking you to authorize the application to access your YouTube account. 

After you authorize it, the terminal will show the progress. You will see a link to your YouTube live stream. Open it, and after a few moments, you should see a **single red dot** in the center of a black screen. 

If a friend follows these same steps, pointing to the same state repository, you will see their dot appear on your stream, and they will see yours on theirs.
