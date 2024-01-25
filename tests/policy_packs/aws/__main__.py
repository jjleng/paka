from pulumi_policy import EnforcementLevel, PolicyPack

from tests.policy_packs.aws.object_store import s3_policies

PolicyPack(
    name="aws",
    enforcement_level=EnforcementLevel.MANDATORY,
    policies=s3_policies,
)
