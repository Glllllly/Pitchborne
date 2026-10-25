# Deploy Pitchborne to Azure Container Apps

For the hackathon demo, run the existing Python web server and Node-based OpenRouter adapter in **one container**. The repository's `Dockerfile` installs both runtimes, and the app serves the UI and API on port `8000`.

## Before deploying

Install the [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli), sign in, and add/update the Container Apps extension. From the repository root:

```powershell
az login
az extension add --name containerapp --upgrade
```

You can smoke-test the same image locally if Docker is available:

```powershell
docker build -t pitchborne:demo .
docker run --rm -p 8000:8000 pitchborne:demo
```

Open <http://127.0.0.1:8000> and <http://127.0.0.1:8000/healthz>. The image deliberately excludes `.env`, generated match data, outputs, and sample videos. Without a key, the match, commentary, statistics, and rule insights still work; live POV generation is unavailable.

## Create a public demo

Choose a unique app name and an Azure region available to your subscription:

```powershell
$PitchborneGroup = "pitchborne-demo-rg"
$PitchborneApp = "pitchborne-demo"
$PitchborneLocation = "eastus"

az containerapp up `
  --name $PitchborneApp `
  --resource-group $PitchborneGroup `
  --location $PitchborneLocation `
  --source . `
  --ingress external `
  --target-port 8000

az containerapp update `
  --name $PitchborneApp `
  --resource-group $PitchborneGroup `
  --min-replicas 1 `
  --max-replicas 1

$PitchborneHostName = az containerapp show `
  --name $PitchborneApp `
  --resource-group $PitchborneGroup `
  --query properties.configuration.ingress.fqdn `
  --output tsv
Write-Output "https://$PitchborneHostName"
```

`az containerapp up` builds from the `Dockerfile` and creates the supporting Azure resources if needed. It is an actual cloud deployment and can incur charges. Use one always-on replica for the demo because job metadata and downloaded video files currently live on that replica's filesystem. A restart or redeployment discards unfinished jobs and cached videos; the synthetic match is regenerated on startup. If persistence becomes necessary, move video/job state to durable storage such as Azure Files or Blob Storage before scaling to multiple replicas.

## Turn on live AI and video

In the Azure portal, open the Container App, then **Security → Secrets**, and add a secret named `openrouter-key` containing your OpenRouter API key. Do not put `.env` in the image or commit the key.

Reference the secret as an environment variable:

```powershell
az containerapp update `
  --name $PitchborneApp `
  --resource-group $PitchborneGroup `
  --set-env-vars OPENROUTER_API_KEY=secretref:openrouter-key
```

If desired, set `OPENROUTER_MODEL`, `OPENROUTER_VIDEO_MODEL`, and `OPENROUTER_TIMEOUT_MS` through additional app environment variables. When they are absent, the code uses the same defaults documented in `.env.example`.

**Protect a key-enabled demo.** Anyone who can reach the public app can ask its endpoints to submit paid video jobs. For a private judging link, use Container Apps' built-in authentication and require sign-in; for an unrestricted public preview, deploy without the key or add a server-side quota before enabling generation. Set an OpenRouter spending limit as a second control.

## Check the deployment

Visit `https://<your-container-app-host>/healthz` and the home page. Then confirm the match starts, switching fan perspective changes the commentary, and a shot-on-target clip is generated when the key is enabled. Container Apps can add default TCP health probes for an ingress-enabled app; the `/healthz` endpoint is available if you want to configure explicit HTTP probes.

## Why Container Apps

Pitchborne is currently one custom Python HTTP server with static assets and a Node SDK subprocess. Container Apps preserves that architecture and allows a Dockerfile, HTTPS ingress, app secrets, and scaling controls. Splitting the UI into Static Web Apps and the API into another service would add cross-origin, routing, and deployment work without helping this demo.
