"""
Snapshot persistence for saving and loading account state.
"""
import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..services.models import Resource, OperationResult, AccountSnapshot
from ..core.exceptions import StateError

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Manages persistence of account snapshots for accurate resume operations."""

    def __init__(self, snapshot_dir: Optional[Path] = None):
        """Initialize the snapshot manager.

        Args:
            snapshot_dir: Directory to store snapshots. Defaults to ~/.aws-hit-breaks/snapshots/
        """
        if snapshot_dir is None:
            snapshot_dir = Path.home() / ".aws-hit-breaks" / "snapshots"

        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, snapshot: AccountSnapshot) -> Path:
        """Save an account snapshot to disk.

        Args:
            snapshot: The account snapshot to save

        Returns:
            Path to the saved snapshot file

        Raises:
            StateError: If saving fails
        """
        try:
            snapshot_data = self._serialize_snapshot(snapshot)

            # Use snapshot_id as filename
            filename = f"{snapshot.snapshot_id}.json"
            filepath = self.snapshot_dir / filename

            # Write atomically via temp file
            temp_file = filepath.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(snapshot_data, f, indent=2, default=str)

            temp_file.replace(filepath)

            logger.info(f"Saved snapshot to {filepath}")
            return filepath

        except Exception as e:
            raise StateError(f"Failed to save snapshot: {e}")

    def load_snapshot(self, snapshot_id: str) -> Optional[AccountSnapshot]:
        """Load a snapshot by ID.

        Args:
            snapshot_id: The snapshot ID to load

        Returns:
            AccountSnapshot if found, None otherwise

        Raises:
            StateError: If loading fails due to corruption
        """
        filepath = self.snapshot_dir / f"{snapshot_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            return self._deserialize_snapshot(data)

        except json.JSONDecodeError as e:
            raise StateError(f"Snapshot file corrupted: {e}")
        except Exception as e:
            raise StateError(f"Failed to load snapshot: {e}")

    def load_latest_snapshot(self, region: Optional[str] = None) -> Optional[AccountSnapshot]:
        """Load the most recent snapshot, optionally filtered by region.

        Args:
            region: Optional region filter

        Returns:
            Most recent AccountSnapshot if found, None otherwise
        """
        snapshots = self.list_snapshots()

        if not snapshots:
            return None

        # Sort by timestamp descending
        snapshots.sort(key=lambda s: s.get('timestamp', ''), reverse=True)

        for snapshot_info in snapshots:
            if region and snapshot_info.get('region') != region:
                continue

            snapshot = self.load_snapshot(snapshot_info['snapshot_id'])
            if snapshot:
                return snapshot

        return None

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots.

        Returns:
            List of snapshot metadata dictionaries
        """
        snapshots = []

        for filepath in self.snapshot_dir.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)

                snapshots.append({
                    'snapshot_id': data.get('snapshot_id'),
                    'timestamp': data.get('timestamp'),
                    'region': data.get('region'),
                    'resource_count': len(data.get('resources', [])),
                    'total_estimated_savings': data.get('total_estimated_savings', 0)
                })
            except Exception as e:
                logger.warning(f"Failed to read snapshot {filepath}: {e}")
                continue

        return snapshots

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot by ID.

        Args:
            snapshot_id: The snapshot ID to delete

        Returns:
            True if deleted, False if not found
        """
        filepath = self.snapshot_dir / f"{snapshot_id}.json"

        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted snapshot {snapshot_id}")
            return True

        return False

    def cleanup_old_snapshots(self, keep_count: int = 10) -> int:
        """Remove old snapshots, keeping only the most recent ones.

        Args:
            keep_count: Number of snapshots to keep

        Returns:
            Number of snapshots deleted
        """
        snapshots = self.list_snapshots()

        if len(snapshots) <= keep_count:
            return 0

        # Sort by timestamp descending
        snapshots.sort(key=lambda s: s.get('timestamp', ''), reverse=True)

        # Delete oldest snapshots
        deleted = 0
        for snapshot_info in snapshots[keep_count:]:
            if self.delete_snapshot(snapshot_info['snapshot_id']):
                deleted += 1

        return deleted

    def _serialize_snapshot(self, snapshot: AccountSnapshot) -> Dict[str, Any]:
        """Serialize an AccountSnapshot to a dictionary."""
        return {
            'snapshot_id': snapshot.snapshot_id,
            'timestamp': snapshot.timestamp.isoformat(),
            'region': snapshot.resources[0].region if snapshot.resources else None,
            'resources': [self._serialize_resource(r) for r in snapshot.resources],
            'original_states': snapshot.original_states,
            'operation_results': [self._serialize_operation_result(r) for r in snapshot.operation_results],
            'total_estimated_savings': snapshot.total_estimated_savings
        }

    def _serialize_resource(self, resource: Resource) -> Dict[str, Any]:
        """Serialize a Resource to a dictionary."""
        return {
            'service_type': resource.service_type,
            'resource_id': resource.resource_id,
            'region': resource.region,
            'current_state': resource.current_state,
            'tags': resource.tags,
            'metadata': resource.metadata,
            'cost_per_hour': resource.cost_per_hour
        }

    def _serialize_operation_result(self, result: OperationResult) -> Dict[str, Any]:
        """Serialize an OperationResult to a dictionary."""
        return {
            'success': result.success,
            'resource': self._serialize_resource(result.resource),
            'operation': result.operation,
            'message': result.message,
            'timestamp': result.timestamp.isoformat(),
            'duration': result.duration
        }

    def _deserialize_snapshot(self, data: Dict[str, Any]) -> AccountSnapshot:
        """Deserialize a dictionary to an AccountSnapshot."""
        resources = [self._deserialize_resource(r) for r in data.get('resources', [])]
        operation_results = [
            self._deserialize_operation_result(r)
            for r in data.get('operation_results', [])
        ]

        return AccountSnapshot(
            snapshot_id=data['snapshot_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            resources=resources,
            original_states=data.get('original_states', {}),
            operation_results=operation_results,
            total_estimated_savings=data.get('total_estimated_savings', 0.0)
        )

    def _deserialize_resource(self, data: Dict[str, Any]) -> Resource:
        """Deserialize a dictionary to a Resource."""
        return Resource(
            service_type=data['service_type'],
            resource_id=data['resource_id'],
            region=data['region'],
            current_state=data['current_state'],
            tags=data.get('tags', {}),
            metadata=data.get('metadata', {}),
            cost_per_hour=data.get('cost_per_hour')
        )

    def _deserialize_operation_result(self, data: Dict[str, Any]) -> OperationResult:
        """Deserialize a dictionary to an OperationResult."""
        return OperationResult(
            success=data['success'],
            resource=self._deserialize_resource(data['resource']),
            operation=data['operation'],
            message=data['message'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            duration=data.get('duration')
        )
