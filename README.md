# Synapse

A decentralized, collaborative live stream powered by YouTube and GitHub.

> This project turns a YouTube channel into a real-time canvas showing a network of all active participants. The state of the network is managed transparently in a public GitHub repository.

### How it Works

Each participant runs a `synapse-node` application, which connects to YouTube and a shared GitHub repository. The application then streams a real-time visualization of the network organism.

This visualization is a dynamic, physics-based graph where:

- **Each node is a participant:** Nodes float and arrange themselves organically, repelling each other while being drawn toward the center.
- **Node size represents age:** New nodes start small and grow over time, giving a sense of history to the network.
- **Connections are dynamic:** Each node automatically connects to its nearest neighbors, creating an ever-shifting web that reflects the network's topology.
- **The network is alive:** When new nodes join, messages appear. Periodically, you'll see pulses of light travel between nodes, representing a flow of information and keeping the visualization active and engaging.

---

### Quick Start

You can run your own `synapse-node` in just a few steps using Docker.

**Prerequisites:**
*   [Docker](https://www.docker.com/get-started) and Docker Compose
*   [Git](https://git-scm.com/downloads)
*   A YouTube Account

#### Step 1: Create the State Repository

1.  Create a new, **public** GitHub repository. This repository will be used to store the shared state of the network. You can leave it empty.

2.  **Add the Cleanup Workflow:** For the network to stay healthy, it's critical to add an automated cleanup process. Create a file in your new state repository at the path `.github/workflows/cleanup.yml` and paste the content below. This GitHub Action will run every 5 minutes to remove inactive nodes and expired events.

    <details>
    <summary>Click to expand `cleanup.yml` content</summary>

    ```yaml
    name: Cleanup Stale Nodes and Events

    on:
      schedule:
        - cron: '*/5 * * * *' # Runs every 5 minutes
      workflow_dispatch:

    jobs:
      cleanup:
        runs-on: ubuntu-latest
        steps:
          - name: Checkout repository
            uses: actions/checkout@v4

          - name: Cleanup stale files
            run: |
              CURRENT_TIMESTAMP=$(date +%s)
              
              # --- 1. Cleanup Stale Nodes ---
              STALE_NODE_SECONDS=300 # 5 minutes
              NODES_DIR="nodes"
              if [ -d "$NODES_DIR" ]; then
                find $NODES_DIR -name "*.json" | while read -r file; do
                  NODE_TIMESTAMP=$(grep -o '"timestamp": [0-9]*' "$file" | sed 's/[^0-9]*//g')
                  if [ -z "$NODE_TIMESTAMP" ] || [ $((CURRENT_TIMESTAMP - NODE_TIMESTAMP)) -gt $STALE_NODE_SECONDS ]; then
                    echo "Removing inactive node: $file"
                    git rm "$file"
                  fi
                done
              fi

              # --- 2. Cleanup Expired Events ---
              EVENTS_DIR="events"
              if [ -d "$EVENTS_DIR" ]; then
                find $EVENTS_DIR -name "*.json" | while read -r file; do
                  EVENT_TIMESTAMP=$(grep -o '"timestamp": [0-9]*' "$file" | sed 's/[^0-9]*//g')
                  EVENT_TTL=$(grep -o '"ttl": [0-9]*' "$file" | sed 's/[^0-9]*//g')
                  [ -z "$EVENT_TTL" ] && EVENT_TTL=60 # Default TTL

                  if [ -z "$EVENT_TIMESTAMP" ] || [ $((CURRENT_TIMESTAMP)) -gt $((EVENT_TIMESTAMP + EVENT_TTL)) ]; then
                    echo "Removing expired event: $file"
                    git rm "$file"
                  fi
                done
              fi

          - name: Commit and push changes
            run: |
              git config --global user.name 'github-actions[bot]'
              git config --global user.email 'github-actions[bot]@users.noreply.github.com'
              
              if ! git diff --cached --quiet; then
                git commit -m "chore: Cleanup stale nodes and events"
                git push
                echo "Cleanup complete. Changes pushed."
              else
                echo "No files to clean up."
              fi
    ```
    </details>

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

After you authorize it, the terminal will show the progress. You will see a link to your YouTube live stream. Open it, and after a few moments, you should see a **single, small red dot** appear in the center of a black screen. This is your node. Watch as it slowly grows to its full size.

If a friend follows these same steps, pointing to the same state repository, you will see their node appear on your stream! The two nodes will float apart, and a connection will form between them. As more nodes join, the network will come to life as a dynamic, floating organism. You will see connections shift, and from time to time, pulses of light will travel between the nodes, showing the network is alive.

---

### License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.