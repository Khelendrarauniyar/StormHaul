from __future__ import annotations


class ProviderError(Exception):
    pass


class RoutingProviderError(ProviderError):
    pass


class GeocodingError(ProviderError):
    pass


class GeocodingNotFound(GeocodingError):
    pass


class WeatherProviderError(ProviderError):
    pass
