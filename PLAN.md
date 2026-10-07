
You are building an MCP server to facilitate agent access to an API.

Use Python with FastAPI, and any appropriate libraries, use a virtualenv setup.
The MCP server must support multiple, simultaneous sessions. Ideally, use the stateless
version of MCP as per 2026-07-28.

The MCP server does not require authentication.

The MCP server will provide AI agents with read access to the WorldCat Search API, 
which is described in `openapi-external-prod.yaml` in this directory.
More documentation can be found at https://developer.api.oclc.org/wcv2
I have saved a copy of that site in `wcv2.html` and `wcv2_files/`.

The entire server will be deployed under `MCP_URL` via https which is part of a
K8s cluster.  You must use namespace `vtlib`, which you should assume to exist (don't try
creating it), and you need to use the kubeconfig file `endeavour.yaml` to access it.  
Use a kustomize-style setup for your k8s/ file.
Note: you don't have to worry about TLS termination/certificates, this is automatically
handled for all subdomains of *.endeavour.cs.vt.edu.

Use a configMapGenerator and a secretGenerator as appropriate; create scripting to 
derive those files' content from .env.  The .env shall be the source of all truth.
Create a .env.sample for documentation.  Make sure to keep everything sensitive/custom 
outside of git and in .gitignore.

Make sure to include liveness and health check in the container.

Write documentation in docs/

Include documentation on how to build, test, and run the container locally.

When done, deploy the server on the endeavour k8s cluster. 
Note that you are logged into container.cs.vt.edu already with an account that has
write privileges. This is different from the deploy token in .env, which has only
read privileges so that k8s can pull the image.
