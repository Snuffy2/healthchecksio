# HealthChecks.io Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]
[![HACS][hacs-shield]][hacs]

Monitor your [Healthchecks.io][healthchecksio] checks directly in Home Assistant. The integration can create entities for your checks and optionally ping one check every five minutes to monitor Home Assistant itself.

![Example Home Assistant entities](example.png)

## Features

- Creates sensors, binary sensors, or both for checks in a Healthchecks.io project.
- Optionally pings a selected check every five minutes.
- Supports the hosted Healthchecks.io service and self-hosted instances.
- Configures entirely through the Home Assistant UI.

## Installation

1. In Home Assistant, open HACS.
2. Open the three-dot menu and select **Custom repositories**.
3. Add `https://github.com/Snuffy2/healthchecksio` and select the **Integration** category.
4. Find **HealthChecks.io (by Snuffy2)** in HACS and select **Download**.
5. Restart Home Assistant if prompted.

For more detail, see the [HACS custom repository instructions][hacs-custom-repositories].

## Configuration

1. In Home Assistant, go to **Settings** → **Devices & services**.
2. Select **Add integration**, then search for **HealthChecks.io (by Snuffy2)**.
3. Enter the requested details.

### API key

Enter a read-write API key for the Healthchecks.io project you want to monitor. Create or view project API keys in **Project Settings** in Healthchecks.io.

### Ping UUID

Optional. Enter the UUID of a Healthchecks.io check when you want Home Assistant to ping that check every five minutes. This is useful for monitoring Home Assistant itself.

### Entity types

Select **Create Binary Sensors**, **Create Sensors**, or both. At least one entity type is required.

### Self-hosted instances

Enable **Use self-hosted instance** to configure a self-hosted Healthchecks.io server:

- **Site Root**: The full base URL of the instance, including `http://` or `https://`.
- **Ping Endpoint**: The full base URL used for pings, for example `https://healthchecks.example.com/ping`. The integration appends the Ping UUID when it sends a ping.

Leave this option disabled for the hosted service. It uses `https://healthchecks.io` for check data and `https://hc-ping.com` for pings.

## How it works

The integration refreshes Healthchecks.io check data every five minutes. When a Ping UUID is configured, it sends that ping before refreshing the entities. Sensors report the check status, and binary sensors provide a quick connectivity-style view of each check.

## Support and contributions

- Report problems or request features through the [issue tracker][issues].
- Contributions are welcome. See the [contribution guidelines](CONTRIBUTING.md).

## Prior Contributions

- Forked from [custom-components/healthchecksio](https://github.com/custom-components/healthchecksio)
- Current Author: [Snuffy2](https://github.com/Snuffy2)

## License

This project is available under the [MIT License][license].

[commits-shield]: https://img.shields.io/github/commit-activity/y/Snuffy2/healthchecksio.svg?style=for-the-badge
[commits]: https://github.com/Snuffy2/healthchecksio/commits/main
[hacs-custom-repositories]: https://www.hacs.xyz/docs/faq/custom_repositories/
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[hacs]: https://hacs.xyz/
[healthchecksio]: https://healthchecks.io/
[issues]: https://github.com/Snuffy2/healthchecksio/issues
[license-shield]: https://img.shields.io/github/license/Snuffy2/healthchecksio.svg?style=for-the-badge
[license]: LICENSE
[releases-shield]: https://img.shields.io/github/release/Snuffy2/healthchecksio.svg?style=for-the-badge
[releases]: https://github.com/Snuffy2/healthchecksio/releases
