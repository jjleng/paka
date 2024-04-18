from __future__ import annotations

from typing import List

from pulumi_policy import (
    Policy,
    ReportViolation,
    ResourceValidationArgs,
    ResourceValidationPolicy,
    StackValidationArgs,
    StackValidationPolicy,
)

max_num_buckets = 1


def s3_count_validator(
    stack: StackValidationArgs, report_violation: ReportViolation
) -> None:
    s3_resources = filter(
        (lambda resource: resource.resource_type == "aws:s3/bucket:Bucket"),
        stack.resources,
    )

    buckets = list(s3_resources)
    if len(buckets) > max_num_buckets:
        report_violation(
            f"No more than {max_num_buckets} bucket(s) should be created.", None
        )


s3_count_check = StackValidationPolicy(
    name="s3-count-check",
    description="Checks the number of buckets created.",
    validate=s3_count_validator,
)


def s3_no_public_read_validator(
    args: ResourceValidationArgs, report_violation: ReportViolation
) -> None:
    if args.resource_type == "aws:s3/bucket:Bucket" and "acl" in args.props:
        acl = args.props["acl"]
        if acl == "public-read" or acl == "public-read-write":
            report_violation(
                "You cannot set public-read or public-read-write on an S3 bucket. "
                + "Read more about ACLs here: https://docs.aws.amazon.com/AmazonS3/latest/dev/acl-overview.html",
                None,
            )


s3_no_public_read = ResourceValidationPolicy(
    name="s3-no-public-read",
    description="Prohibits setting the publicRead or publicReadWrite permission on AWS S3 buckets.",
    validate=s3_no_public_read_validator,
)


def s3_force_destroy_validator(
    args: ResourceValidationArgs, report_violation: ReportViolation
) -> None:
    if args.resource_type == "aws:s3/bucket:Bucket" and "forceDestroy" in args.props:
        force_destroy = args.props["forceDestroy"]
        if not force_destroy:
            report_violation(
                "You must set forceDestroy to true. "
                + "Read more about forceDestroy here: https://www.pulumi.com/docs/intro/concepts/resources/#deletion",
                None,
            )


s3_force_destroy = ResourceValidationPolicy(
    name="s3-force-destroy",
    description="Requires forceDestroy to be set to true.",
    validate=s3_force_destroy_validator,
)

s3_policies: List[Policy] = [s3_count_check, s3_no_public_read, s3_force_destroy]
