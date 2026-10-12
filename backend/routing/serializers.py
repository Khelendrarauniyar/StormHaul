from rest_framework import serializers


class RoutePlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure_at = serializers.DateTimeField()
    load_weight_lb = serializers.IntegerField(min_value=1, max_value=500_000)
    checkpoint_interval_miles = serializers.ChoiceField(
        choices=[10, 25, 50], default=25
    )
    origin_latitude = serializers.FloatField(
        required=False, allow_null=True, min_value=-90, max_value=90
    )
    origin_longitude = serializers.FloatField(
        required=False, allow_null=True, min_value=-180, max_value=180
    )
    destination_latitude = serializers.FloatField(
        required=False, allow_null=True, min_value=-90, max_value=90
    )
    destination_longitude = serializers.FloatField(
        required=False, allow_null=True, min_value=-180, max_value=180
    )

    def validate_origin(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Origin is required.")
        return value

    def validate_destination(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Destination is required.")
        return value

    def validate(self, attrs):
        if attrs["origin"].lower() == attrs["destination"].lower():
            raise serializers.ValidationError(
                {"destination": "Destination must differ from the origin."}
            )
        for prefix in ("origin", "destination"):
            latitude = attrs.get(f"{prefix}_latitude")
            longitude = attrs.get(f"{prefix}_longitude")
            if (latitude is None) != (longitude is None):
                raise serializers.ValidationError(
                    {
                        prefix: "Provide both latitude and longitude, or neither."
                    }
                )
        return attrs
