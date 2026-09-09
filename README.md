# Kubernetes Production Capstone

A production-style Flask + PostgreSQL application deployed on Amazon EKS using Helm, Amazon ECR, Kubernetes RBAC, NetworkPolicy, HPA, persistent EBS storage, and GitHub Actions CI/CD.

## Architecture

```text
GitHub
   |
git push
   |
GitHub Actions
   |---------------- AWS OIDC ----------------> IAM Role
   |
Docker build
   |
   v
Amazon ECR
   |
Helm upgrade --install
   |
   v
Amazon EKS
   |
   +-------------------+-------------------+
   |                   |                   |
Flask Deployment   PostgreSQL         HPA
                   StatefulSet
                       |
                      PVC
                       |
                      EBS
```

## Technologies

- Python / Flask
- PostgreSQL 16
- Docker
- Kubernetes
- Helm
- Amazon EKS
- Amazon ECR
- Amazon EBS
- AWS IAM
- GitHub Actions
- GitHub OIDC
- Kubernetes RBAC
- Kubernetes NetworkPolicy
- Horizontal Pod Autoscaler (HPA)

## Project Structure

```text
kubernetes-production-capstone/
├── app.py
├── requirements.txt
├── Dockerfile
├── helm/
│   └── flask-postgres/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       ├── values-staging.yaml
│       ├── values-prod.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── postgres-service.yaml
│           ├── secret.yaml
│           ├── statefulset.yaml
│           ├── serviceaccount.yaml
│           ├── role.yaml
│           ├── rolebinding.yaml
│           ├── networkpolicy.yaml
│           └── hpa.yaml
├── github-actions-role.yaml
├── github-actions-rolebinding.yaml
└── .github/
    └── workflows/
        └── deploy.yml
```

## Application

The Flask application exposes:

- `/` — application endpoint
- `/db` — PostgreSQL connectivity test

The application listens on port `5006`.

Database settings are supplied through:

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

## Docker

The EKS worker nodes are AMD64 while the development Mac is Apple Silicon, so production images are built explicitly for Linux AMD64:

```bash
docker build --platform linux/amd64 -t kubernetes-flask:v3 .
```

The GitHub Actions pipeline uses the same platform setting.

## Helm

Helm packages the Kubernetes application into a reusable chart.

The chart contains templates for:

- Flask Deployment
- Flask Service
- PostgreSQL StatefulSet
- PostgreSQL headless Service
- Secret
- ServiceAccount
- Role
- RoleBinding
- NetworkPolicy
- HPA

Environment-specific configuration is provided through:

```text
values.yaml
values-dev.yaml
values-staging.yaml
values-prod.yaml
```

Example:

```bash
helm install eks-prod ./helm/flask-postgres   --namespace production   --create-namespace
```

Inspect the release:

```bash
helm list -n production
helm status eks-prod -n production
```

Final validation showed the `eks-prod` release as `deployed`.

## PostgreSQL StatefulSet and Persistent Storage

PostgreSQL runs as a StatefulSet:

```text
eks-prod-flask-postgres-postgres-0
```

It uses a headless Service:

```text
eks-prod-flask-postgres-postgres-service
```

Persistent storage is created through `volumeClaimTemplates`.

Final PVC:

```text
postgres-storage-eks-prod-flask-postgres-postgres-0
```

Final storage state:

```text
Status:       Bound
Capacity:     1Gi
Access mode:  RWO
StorageClass: gp2
```

The AWS EBS CSI driver provisions the EBS-backed volume.

### PostgreSQL PGDATA

The EBS filesystem contains `lost+found`, so PostgreSQL uses:

```text
PGDATA=/var/lib/postgresql/data/pgdata
```

This allowed PostgreSQL to initialize successfully while retaining persistent storage.

## Kubernetes RBAC

The Flask application uses:

```text
ServiceAccount: eks-prod-flask-postgres-flask
```

Its application Role follows least privilege and allows access to ConfigMaps.

GitHub Actions uses:

```text
IAM Role: GitHubActionsEKSDeployRole
Kubernetes Group: github-actions-deployer
```

The IAM role is mapped to EKS through an access entry, then authorized inside the `production` namespace through a Kubernetes RoleBinding.

The deployment identity is intentionally not allowed to create Kubernetes Roles, preventing it from granting itself broader RBAC privileges.

## NetworkPolicy

The PostgreSQL NetworkPolicy selects:

```text
app=postgres
```

and permits TCP port `5432` only from Pods labeled:

```text
app=flask
```

A temporary Pod without the Flask label was unable to connect to PostgreSQL, while Flask continued to connect successfully.

EKS VPC CNI network-policy enforcement had to be enabled for the policy to take effect.

## Horizontal Pod Autoscaler

Flask resources:

```yaml
requests:
  cpu: 100m
  memory: 128Mi

limits:
  cpu: 500m
  memory: 256Mi
```

HPA:

```text
Minimum replicas: 1
Maximum replicas: 3
Target CPU:       70%
```

CPU load testing successfully scaled Flask from 1 to 3 replicas.

## Amazon EKS

Cluster:

```text
Name:    kubernetes-production
Region:  ap-south-1
Version: 1.36
```

Managed node group:

```text
Name:             production-nodes
Instance type:    t3.medium
Desired capacity: 2
Minimum:          2
Maximum:          2
```

The cluster uses VPC CNI, CoreDNS, kube-proxy, Metrics Server, and the AWS EBS CSI driver.

## Amazon ECR

Repository:

```text
kubernetes-flask
```

Production images are tagged using the GitHub commit SHA:

```text
kubernetes-flask:<git-sha>
```

This provides traceability between a deployed image and its source commit.

## GitHub Actions CI/CD

The workflow runs on pushes to `main`.

```text
git push
   |
   v
GitHub Actions
   |
   +--> Checkout
   |
   +--> AWS OIDC authentication
   |
   +--> Login to ECR
   |
   +--> Docker build --platform linux/amd64
   |
   +--> Push image to ECR
   |
   +--> Update EKS kubeconfig
   |
   +--> helm upgrade --install
   |
   v
EKS
```

GitHub OIDC is used instead of storing long-lived AWS access keys.

## Final CI/CD Validation

The Flask response was changed to:

```text
Flask application v2 is running on EKS!
```

After committing and pushing the change:

```bash
git add app.py
git commit -m "update Flask application message"
git push origin main
```

GitHub Actions successfully:

1. Authenticated to AWS through OIDC.
2. Built the Docker image.
3. Pushed the image to ECR.
4. Connected to EKS.
5. Ran Helm upgrade.
6. Updated the Flask Deployment.
7. Started the new Flask Pod.

The deployed application returned:

```text
Flask application v2 is running on EKS!
```

The database endpoint returned:

```text
PostgreSQL connection successful!
PostgreSQL 16.15 ...
```

This proved the complete source-to-production deployment path.

## Final Production State

```text
Flask Pod:          1/1 Running
PostgreSQL Pod:     1/1 Running
StatefulSet:        1/1 Ready
PVC:                Bound
HPA:                1-3 replicas
NetworkPolicy:      Active
Helm release:       deployed
GitHub Actions:     successful
Git working tree:   clean
```

## Troubleshooting Lessons

### Apple Silicon vs AMD64

The initial image did not run on the AMD64 EKS nodes because it was built for the local Mac architecture.

Solution:

```bash
docker build --platform linux/amd64 ...
```

### EBS CSI Driver

The PostgreSQL PVC remained Pending until the AWS EBS CSI driver was enabled.

### PostgreSQL `lost+found`

PostgreSQL could not initialize when the EBS filesystem root was used directly.

Solution:

```text
PGDATA=/var/lib/postgresql/data/pgdata
```

### NetworkPolicy Enforcement

The NetworkPolicy required VPC CNI network-policy enforcement and the appropriate AWS permissions.

### GitHub OIDC

The initial GitHub OIDC trust policy did not match the repository's immutable OIDC subject. Correcting the trust relationship allowed GitHub Actions to authenticate without AWS access keys.

### EKS RBAC

AWS IAM authentication and Kubernetes authorization are separate. The GitHub IAM role was authenticated by EKS but initially lacked Kubernetes permissions required by Helm. The EKS access entry, Kubernetes group, Role, and RoleBinding solved this while keeping access scoped to `production`.

## Useful Commands

```bash
kubectl get pods -n production
kubectl get svc -n production
kubectl get statefulset -n production
kubectl get pvc -n production
kubectl get hpa -n production
kubectl get networkpolicy -n production
kubectl get role,rolebinding,serviceaccount -n production
helm list -n production
helm status eks-prod -n production
```

Application test:

```bash
kubectl port-forward   -n production   service/eks-prod-flask-postgres-flask-service   5007:5006
```

Then:

```bash
curl http://localhost:5007/
curl http://localhost:5007/db
```

## Security Notes

The PostgreSQL password in `templates/secret.yaml` is suitable only for this learning project.

For a real production system, plaintext secrets should not be committed to Git. A stronger implementation would use AWS Secrets Manager or another external secret-management mechanism.

The GitHub Actions deployment role is namespace-scoped and does not have unrestricted Kubernetes administrator permissions.

## Cleanup / Cost Control

AWS resources can incur charges while running.

Inspect the environment:

```bash
aws eks describe-cluster   --name kubernetes-production   --region ap-south-1

kubectl get all -n production
kubectl get pvc -n production
```

When the environment is no longer needed, delete the EKS environment and associated resources using the appropriate infrastructure-management commands.

The GitHub repository and source code can remain after AWS infrastructure is removed.

## What This Project Demonstrates

- Docker containerization
- Kubernetes workload management
- Helm packaging
- Environment-specific configuration
- Stateful workloads
- Persistent EBS storage
- Kubernetes networking
- Network security
- RBAC and least privilege
- Autoscaling
- Amazon EKS
- Amazon ECR
- AWS IAM
- GitHub OIDC
- GitHub Actions
- Continuous deployment
- Production troubleshooting

## Interview Summary

> Built and deployed a Flask/PostgreSQL production-style application on Amazon EKS using Helm, ECR and GitHub Actions. GitHub authenticates to AWS through OIDC, Docker images are tagged with Git commit SHAs, and Helm performs automated deployments. PostgreSQL runs as a StatefulSet with persistent EBS storage, Flask uses HPA for scaling, Kubernetes RBAC applies least privilege, and a NetworkPolicy restricts PostgreSQL access to Flask Pods.
