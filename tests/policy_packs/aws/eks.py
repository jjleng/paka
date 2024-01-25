from pulumi_policy import (
    ReportViolation,
    ResourceValidationArgs,
    ResourceValidationPolicy,
)


def model_group_validator(
    args: ResourceValidationArgs, report_violation: ReportViolation
) -> None:
    if args.resource_type == "aws:eks/nodeGroup:NodeGroup":
        instance_type = args.props["instanceTypes"][0]

        if instance_type == "c7a.xlarge":
            if "taints" in args.props:
                taints = args.props["taints"]

                # Verify that taint {key: app, value: model-group, effect: NoSchedule} exists
                exists = False
                for i in range(len(taints)):
                    taint = taints[i]
                    if (
                        taint["key"] == "app"
                        and taint["value"] == "model-group"
                        and taint["effect"] == "NO_SCHEDULE"
                    ):
                        exists = True
                if not exists:
                    report_violation(
                        "Taint {key: app, value: model-group, effect: NoSchedule} is not set for model-group node group.",
                        None,
                    )

                # Verify that taint {key: model, value: <model-group-name>, effect: NoSchedule} exists
                exists = False
                for i in range(len(taints)):
                    taint = taints[i]
                    if (
                        taint["key"] == "model"
                        and taint["value"] == "llama2-7b"
                        and taint["effect"] == "NO_SCHEDULE"
                    ):
                        exists = True
                if not exists:
                    report_violation(
                        "Taint {key: model, value: <model-group-name>, effect: NoSchedule} is not set for model-group node group.",
                        None,
                    )


model_group_taints = ResourceValidationPolicy(
    name="model-group-taints",
    description="Model group should have taints.",
    validate=model_group_validator,
)
