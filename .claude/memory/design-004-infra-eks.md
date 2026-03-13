# EKS 인프라 설계

> **상태**: 활성 — 구현 대기 (Phase 3 후)
> **마지막 갱신**: 2026-03-14

## 1. 레포 구조

```
~/individual/stock/                  # 상위 디렉토리
├── kiwoom-autotrade/                # 앱 레포
│   ├── src/
│   ├── frontend/
│   ├── scripts/
│   ├── docker/
│   │   ├── Dockerfile.trading       # trading 서비스 이미지
│   │   ├── Dockerfile.data-pipeline # 데이터 파이프라인 이미지
│   │   └── Dockerfile.frontend      # Next.js 이미지
│   ├── docker-compose.yml           # 로컬 개발용
│   └── .github/workflows/
│       ├── pr-check.yml             # 기존 PR 체크 (lint + test + security)
│       └── build-push.yml           # main 머지 시 Docker 빌드 → ECR push
│
└── kiwoom-infra/                    # 인프라 레포 (신규)
    ├── terraform/
    ├── k8s/
    ├── helm-values/
    ├── argocd/
    ├── scripts/
    ├── CLAUDE.md
    └── .github/workflows/
```

## 2. 인프라 레포 상세 구조 (kiwoom-infra)

```
kiwoom-infra/
│
├── terraform/
│   ├── environments/
│   │   ├── prod/
│   │   │   ├── main.tf              # 프로덕션 환경 진입점
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   ├── terraform.tfvars     # (.gitignore) 실제 값
│   │   │   └── backend.tf           # S3 + DynamoDB state 관리
│   │   └── dev/                     # 개발/테스트용 (선택)
│   │       └── ...
│   │
│   └── modules/                     # 재사용 모듈
│       ├── vpc/
│       │   ├── main.tf              # VPC, Subnet, NAT, IGW
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── eks/
│       │   ├── main.tf              # EKS 클러스터, 노드그룹, IRSA
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── rds/
│       │   ├── main.tf              # RDS PostgreSQL
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── elasticache/
│       │   ├── main.tf              # ElastiCache Redis
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── ecr/
│       │   ├── main.tf              # ECR 레포지토리 (trading, data-pipeline, frontend)
│       │   ├── variables.tf
│       │   └── outputs.tf
│       └── secrets/
│           ├── main.tf              # Secrets Manager (API 키, DB 비번)
│           ├── variables.tf
│           └── outputs.tf
│
├── k8s/
│   └── apps/                        # 내 서비스 — Kustomize
│       ├── trading/
│       │   ├── base/
│       │   │   ├── kustomization.yaml
│       │   │   ├── deployment.yaml
│       │   │   ├── service.yaml
│       │   │   └── configmap.yaml
│       │   └── overlays/
│       │       ├── dev/
│       │       │   └── kustomization.yaml   # 리소스 축소, 리플리카 1
│       │       └── prod/
│       │           └── kustomization.yaml   # 리소스 확대
│       ├── data-pipeline/
│       │   ├── base/
│       │   └── overlays/
│       └── frontend/
│           ├── base/
│           └── overlays/
│
├── helm-values/                      # 외부 Helm 차트 커스텀 설정
│   ├── argocd-values.yaml            # ArgoCD 차트 설정
│   └── airflow-values.yaml           # Airflow 차트 설정
│
├── argocd/                           # ArgoCD Application 정의
│   ├── app-of-apps.yaml              # App of Apps 패턴 (모든 앱 관리)
│   ├── apps/
│   │   ├── trading.yaml              # → k8s/apps/trading/ 감시
│   │   ├── data-pipeline.yaml        # → k8s/apps/data-pipeline/ 감시
│   │   ├── frontend.yaml             # → k8s/apps/frontend/ 감시
│   │   └── airflow.yaml              # → helm-values/airflow-values.yaml 참조
│   └── projects/
│       └── kiwoom.yaml               # ArgoCD 프로젝트 정의
│
├── scripts/
│   ├── bootstrap.sh                  # 초기 설정 (terraform init + ArgoCD 설치)
│   ├── destroy.sh                    # 전체 해체
│   └── port-forward.sh               # 로컬에서 ArgoCD UI 접속
│
└── .github/workflows/
    └── terraform.yml                 # terraform plan (PR) / apply (main)
```

## 3. Terraform 모듈별 역할

| 모듈 | 리소스 | 비고 |
|------|--------|------|
| **vpc** | VPC, Public/Private Subnet, NAT Gateway, IGW, Route Table | 서울 리전 (ap-northeast-2), AZ 2개 |
| **eks** | EKS 클러스터, Managed Node Group, OIDC Provider, IRSA | t3.medium, Karpenter로 오토스케일링 |
| **rds** | RDS PostgreSQL, Subnet Group, Security Group | db.t3.micro, Private Subnet |
| **elasticache** | ElastiCache Redis, Subnet Group, Security Group | cache.t3.micro, Private Subnet |
| **ecr** | ECR 레포 3개 (trading, data-pipeline, frontend) | 이미지 수명주기 정책 포함 |
| **secrets** | Secrets Manager (키움 API 키, DB 비밀번호 등) | k8s External Secrets Operator로 주입 |

## 4. Terraform State 관리

```hcl
# backend.tf
terraform {
  backend "s3" {
    bucket         = "kiwoom-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "ap-northeast-2"
    dynamodb_table = "kiwoom-terraform-locks"
    encrypt        = true
  }
}
```

- S3: state 파일 저장 (버저닝 + 암호화)
- DynamoDB: state locking (동시 수정 방지)
- 이 S3/DynamoDB는 수동 생성 또는 별도 bootstrap으로 1회 생성

## 5. 배포 흐름

### 초기 세팅 (1회)
```
1. scripts/bootstrap.sh 실행
2. terraform apply → VPC + EKS + RDS + ElastiCache + ECR 생성
3. kubectl 설정 (aws eks update-kubeconfig)
4. helm install argocd → ArgoCD 설치
5. kubectl apply -f argocd/app-of-apps.yaml → ArgoCD가 전체 앱 감시 시작
```

### 앱 코드 변경 시
```
1. kiwoom-autotrade에서 코드 수정 → main 머지
2. GitHub Actions (build-push.yml) → Docker 빌드 → ECR push
3. kiwoom-infra의 k8s/apps/trading/base/deployment.yaml 이미지 태그 업데이트
4. ArgoCD가 감지 → 자동 배포
```

### 인프라 변경 시
```
1. kiwoom-infra에서 terraform 수정 → PR 생성
2. GitHub Actions → terraform plan 결과 PR 코멘트
3. 리뷰 후 main 머지 → terraform apply 자동 실행
```

## 6. 비용 추정 (서울 리전)

| 서비스 | 스펙 | 월 비용 |
|--------|------|---------|
| EKS 컨트롤 플레인 | — | $73 |
| EKS 노드 | t3.medium × 2 | $60 |
| RDS PostgreSQL | db.t3.micro | $15 |
| ElastiCache Redis | cache.t3.micro | $12 |
| ECR | ~2GB 이미지 | $1 |
| NAT Gateway | — | $32 |
| ALB | — | $16 |
| S3 (Terraform state) | <1GB | $0.03 |
| Secrets Manager | 시크릿 5개 | $2 |
| **합계** | | **~$211/월** |

### 비용 절감 옵션
- 장 운영 시간(08:00~16:00)만 노드 운영 → **노드 비용 ~67% 절감**
- Spot 인스턴스 → **노드 비용 ~70% 절감** (data-pipeline에 적합)
- dev 환경 미사용 시 → node 0으로 축소

## 7. 보안

- EKS → Private Subnet, OIDC 기반 IRSA (Pod별 IAM 역할)
- RDS → Private Subnet, Security Group으로 EKS에서만 접근
- ElastiCache → Private Subnet, 암호화 at-rest + in-transit
- Secrets → External Secrets Operator로 k8s Secret 자동 동기화
- ECR → 이미지 스캔 활성화

## 8. 단계적 전환 계획

| 단계 | 시점 | 내용 |
|------|------|------|
| **0단계** (현재) | 지금 | 로컬 Mac + Docker Compose |
| **1단계** | Phase 3 완료 후 | kiwoom-infra 레포 생성 + Terraform 모듈 작성 |
| **2단계** | — | EKS + RDS + ElastiCache 프로비저닝 |
| **3단계** | — | ArgoCD + Airflow 설치, 앱 배포 |
| **4단계** | — | CI/CD 파이프라인 연결 (build-push.yml) |
| **5단계** | — | 모니터링 (Prometheus + Grafana) |

## 9. 디렉토리 구조 (확정)

```
~/individual/stock/
├── kiwoom-autotrade/    # 앱 레포 (현재 위치)
└── kiwoom-infra/        # 인프라 레포 (Phase 3 후 구현)
```

- crontab: `KIWOOM_HOME` 환경변수로 경로 관리
- 이동 완료: 2026-03-14
