from typing import List, Optional

from src.prompts import auto_register_prompt


class ReleasesPrompts:
    """Class containing releases related prompts"""

    @auto_register_prompt
    @staticmethod
    def get_all_releases(
        from_time: Optional[int] = None,
        to_time: Optional[int] = None,
        name_filter: Optional[str] = None,
        page_number: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> str:
        """List all releases with optional filtering and pagination"""
        return f"""
        Get all releases:
        - From time: {from_time or '(not specified)'}
        - To time: {to_time or '(not specified)'}
        - Name filter: {name_filter or '(not specified)'}
        - Page number: {page_number or '(not specified)'}
        - Page size: {page_size or '(not specified)'}
        """

    @auto_register_prompt
    @staticmethod
    def get_release(release_id: str) -> str:
        """Get details of a specific release by ID"""
        return f"""
        Get release details:
        - Release ID: {release_id}
        """

    @auto_register_prompt
    @staticmethod
    def create_release(
        name: str,
        start: int,
        applications: Optional[List[dict]] = None,
        services: Optional[List[dict]] = None
    ) -> str:
        """Create a new release"""
        return f"""
        Create new release:
        - Name: {name}
        - Start time: {start}
        - Applications: {applications or '(not specified)'}
        - Services: {services or '(not specified)'}
        """

    @auto_register_prompt
    @staticmethod
    def update_release(
        release_id: str,
        name: str,
        start: int,
        applications: Optional[List[dict]] = None,
        services: Optional[List[dict]] = None
    ) -> str:
        """Update an existing release"""
        return f"""
        Update release:
        - Release ID: {release_id}
        - Name: {name}
        - Start time: {start}
        - Applications: {applications or '(not specified)'}
        - Services: {services or '(not specified)'}
        """

    @auto_register_prompt
    @staticmethod
    def delete_release(release_id: str) -> str:
        """Delete a release"""
        return f"""
        Delete release:
        - Release ID: {release_id}
        """

    @auto_register_prompt
    @staticmethod
    def analyze_application_performance_after_release(
        release_name: Optional[str] = None,
        release_id: Optional[str] = None,
        application_name: Optional[str] = None,
        time_window: Optional[str] = None
    ) -> str:
        """Analyze how an application is performing after a specific release"""
        if release_name and not release_id:
            lookup_instruction = f"1. Find the release by name using get_all_releases with name_filter='{release_name}'"
        elif release_id:
            lookup_instruction = f"1. Get release details directly using release ID '{release_id}'"
        else:
            lookup_instruction = "1. ERROR: Either release_name or release_id must be provided"

        return f"""
        Analyze application performance after release:
        - Release name: {release_name or '(not specified)'}
        - Release ID: {release_id or '(not specified)'}
        - Application: {application_name or '(will be determined from release)'}
        - Time window: {time_window or '(default: from release start to now)'}

        Steps:
        {lookup_instruction}
        2. Extract the release start time and associated applications from release details
        3. Fetch application metrics (latency, error rates, throughput) from release time to now
        4. Compare metrics before and after the release
        5. Identify any performance degradation or improvements

        Note: If both release_name and release_id are provided, release_id takes precedence.
        """

    @auto_register_prompt
    @staticmethod
    def check_incidents_after_release(
        release_name: Optional[str] = None,
        release_id: Optional[str] = None,
        application_name: Optional[str] = None,
        severity: Optional[str] = None
    ) -> str:
        """Check for new incidents on an application after a specific release"""
        if release_name and not release_id:
            lookup_instruction = f"1. Find the release by name using get_all_releases with name_filter='{release_name}'"
        elif release_id:
            lookup_instruction = f"1. Get release details directly using release ID '{release_id}'"
        else:
            lookup_instruction = "1. ERROR: Either release_name or release_id must be provided"

        return f"""
        Check for incidents after release:
        - Release name: {release_name or '(not specified)'}
        - Release ID: {release_id or '(not specified)'}
        - Application: {application_name or '(will be determined from release)'}
        - Severity filter: {severity or '(all severities)'}

        Steps:
        {lookup_instruction}
        2. Extract the release start time and associated applications from release details
        3. Query incidents/issues that occurred after the release start time
        4. Filter incidents related to the application(s) in the release
        5. Provide a summary of new incidents, their severity, and impact

        Note: If both release_name and release_id are provided, release_id takes precedence.
        """

    @auto_register_prompt
    @staticmethod
    def analyze_kpi_evolution_after_release(
        release_name: Optional[str] = None,
        release_id: Optional[str] = None,
        application_name: Optional[str] = None,
        kpis: Optional[List[str]] = None,
        comparison_period: Optional[str] = None
    ) -> str:
        """Get statistics on how application KPIs evolved after a release"""
        if release_name and not release_id:
            lookup_instruction = f"1. Find the release by name using get_all_releases with name_filter='{release_name}'"
        elif release_id:
            lookup_instruction = f"1. Get release details directly using release ID '{release_id}'"
        else:
            lookup_instruction = "1. ERROR: Either release_name or release_id must be provided"

        return f"""
        Analyze KPI evolution after release:
        - Release name: {release_name or '(not specified)'}
        - Release ID: {release_id or '(not specified)'}
        - Application: {application_name or '(will be determined from release)'}
        - KPIs to track: {kpis or '(default: latency, error_rate, throughput, calls)'}
        - Comparison period: {comparison_period or '(same duration before release)'}

        Steps:
        {lookup_instruction}
        2. Extract the release start time and associated applications from release details
        3. Define pre-release and post-release time windows
        4. Fetch KPI metrics for both periods
        5. Calculate percentage changes and trends
        6. Provide statistical analysis (mean, median, p95, p99)
        7. Highlight significant changes and anomalies

        Note: If both release_name and release_id are provided, release_id takes precedence.
        """

    @classmethod
    def get_prompts(cls):
        """Return all prompts defined in this class"""
        return [
            ('get_all_releases', cls.get_all_releases),
            ('get_release', cls.get_release),
            ('create_release', cls.create_release),
            ('update_release', cls.update_release),
            ('delete_release', cls.delete_release),
            ('analyze_application_performance_after_release', cls.analyze_application_performance_after_release),
            ('check_incidents_after_release', cls.check_incidents_after_release),
            ('analyze_kpi_evolution_after_release', cls.analyze_kpi_evolution_after_release),
        ]
