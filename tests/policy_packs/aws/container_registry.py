from typing import List

from pulumi_policy import (
    Policy,
    ReportViolation,
    ResourceValidationArgs,
    ResourceValidationPolicy,
    StackValidationArgs,
    StackValidationPolicy,
)

max_num_ecrs = 1


def ecr_count_validator(
    stack: StackValidationArgs, report_violation: ReportViolation
) -> None:
    ecr_resources = filter(
        (lambda resource: resource.resource_type == "aws:ecr/repository:Repository"),
        stack.resources,
    )

    ecrs = list(ecr_resources)
    if len(ecrs) > max_num_ecrs:
        report_violation(
            f"No more than {max_num_ecrs} repository(ies) should be created.", None
        )


ecr_count_check = StackValidationPolicy(
    name="ecr-count-check",
    description="Checks the number of ECR repositories created.",
    validate=ecr_count_validator,
)


def ecr_force_delete_validator(
    args: ResourceValidationArgs, report_violation: ReportViolation
) -> None:
    if args.resource_type == "aws:ecr/repository:Repository":
        force_destroy = args.props["forceDelete"]
        if not force_destroy:
            report_violation(
                "You must set forceDelete to true. ",
                None,
            )


ecr_force_delete = ResourceValidationPolicy(
    name="ecr-force-delete",
    description="Requires forceDelete to be set to true.",
    validate=ecr_force_delete_validator,
)

ecr_policies: List[Policy] = [ecr_count_check, ecr_force_delete]
