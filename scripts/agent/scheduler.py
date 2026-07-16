"""
Task Scheduler Module

Planificateur de tâches pour le workflow de refresh.
"""

from datetime import datetime
from heapq import heappush, heappop
from typing import Optional

from _shared.core.models import TaskPriority, ScheduledTask


class TaskScheduler:
    """
    Planificateur de tâches avec file de priorité.

    Gère:
    - File de priorité (heap)
    - Rate limiting pour les APIs
    - Batch processing
    """

    # Limites de rate (requêtes par minute)
    RATE_LIMITS = {
        "gsc": 60,
        "dataforseo": 30,
        "sheets": 100,
    }

    def __init__(self):
        """Initialise le scheduler."""
        self._queue: list[ScheduledTask] = []
        self._processed: set[str] = set()
        self._api_calls: dict[str, list[datetime]] = {
            "gsc": [],
            "dataforseo": [],
            "sheets": [],
        }

    def add_task(
        self,
        url: str,
        blog_id: str,
        action: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        metadata: Optional[dict] = None
    ):
        """
        Ajoute une tâche à la file.

        Args:
            url: URL à traiter
            blog_id: Identifiant du blog
            action: Action à effectuer
            priority: Niveau de priorité
            metadata: Données supplémentaires
        """
        # Éviter les doublons : ni déjà traité, ni déjà en file d'attente.
        # (Avant : seul _processed était vérifié → une même URL pouvait être
        # empilée plusieurs fois dans la file.)
        if url in self._processed:
            return
        if any(t.url == url for t in self._queue):
            return

        # Extraire main_keyword de metadata si disponible
        main_keyword = ""
        if metadata and "main_keyword" in metadata:
            main_keyword = metadata.pop("main_keyword", "")

        task = ScheduledTask(
            priority=priority.value,
            url=url,
            blog_id=blog_id,
            action=action,
            scheduled_at=datetime.now().isoformat(),
            metadata=metadata or {},
            main_keyword=main_keyword,
        )

        heappush(self._queue, task)

    def add_batch(
        self,
        tasks: list[dict],
        default_priority: TaskPriority = TaskPriority.MEDIUM
    ):
        """
        Ajoute un batch de tâches.

        Args:
            tasks: Liste de dicts avec url, blog_id, action, priority (optionnel), main_keyword (optionnel)
            default_priority: Priorité par défaut
        """
        for task in tasks:
            priority = TaskPriority(task.get("priority", default_priority.value))
            # Inclure main_keyword dans metadata
            metadata = task.get("metadata", {}) or {}
            if "main_keyword" in task and task["main_keyword"]:
                metadata["main_keyword"] = task["main_keyword"]

            self.add_task(
                url=task["url"],
                blog_id=task["blog_id"],
                action=task.get("action", "AUDIT"),
                priority=priority,
                metadata=metadata,
            )

    def get_next(self) -> Optional[ScheduledTask]:
        """
        Récupère la prochaine tâche à traiter.

        Returns:
            ScheduledTask ou None si la file est vide
        """
        if not self._queue:
            return None

        task = heappop(self._queue)
        self._processed.add(task.url)
        return task

    def peek(self) -> Optional[ScheduledTask]:
        """
        Regarde la prochaine tâche sans la retirer.

        Returns:
            ScheduledTask ou None
        """
        if not self._queue:
            return None
        return self._queue[0]

    def get_batch(self, size: int = 10) -> list[ScheduledTask]:
        """
        Récupère un batch de tâches.

        Args:
            size: Nombre de tâches à récupérer

        Returns:
            Liste de ScheduledTask
        """
        batch = []
        for _ in range(min(size, len(self._queue))):
            task = self.get_next()
            if task:
                batch.append(task)
        return batch

    def is_empty(self) -> bool:
        """Vérifie si la file est vide."""
        return len(self._queue) == 0

    def size(self) -> int:
        """Retourne la taille de la file."""
        return len(self._queue)

    def clear(self):
        """Vide la file."""
        self._queue.clear()
        self._processed.clear()

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    def can_call_api(self, api_name: str) -> bool:
        """
        Vérifie si on peut appeler une API (rate limiting).

        Args:
            api_name: Nom de l'API (gsc, dataforseo, sheets)

        Returns:
            True si l'appel est autorisé
        """
        if api_name not in self.RATE_LIMITS:
            return True

        now = datetime.now()
        calls = self._api_calls.get(api_name, [])

        # Nettoyer les appels de plus d'une minute
        one_minute_ago = now.timestamp() - 60
        calls = [c for c in calls if c.timestamp() > one_minute_ago]
        self._api_calls[api_name] = calls

        return len(calls) < self.RATE_LIMITS[api_name]

    def record_api_call(self, api_name: str):
        """
        Enregistre un appel API.

        Args:
            api_name: Nom de l'API
        """
        if api_name not in self._api_calls:
            self._api_calls[api_name] = []
        self._api_calls[api_name].append(datetime.now())

    def get_wait_time(self, api_name: str) -> float:
        """
        Calcule le temps d'attente avant le prochain appel.

        Args:
            api_name: Nom de l'API

        Returns:
            Temps d'attente en secondes (0 si immédiat)
        """
        if self.can_call_api(api_name):
            return 0.0

        calls = self._api_calls.get(api_name, [])
        if not calls:
            return 0.0

        # Temps depuis le plus ancien appel dans la fenêtre
        oldest = min(calls, key=lambda c: c.timestamp())
        wait = 60 - (datetime.now().timestamp() - oldest.timestamp())
        return max(0.0, wait)

    # =========================================================================
    # Statistiques
    # =========================================================================

    def get_stats(self) -> dict:
        """
        Retourne les statistiques du scheduler.

        Returns:
            Dictionnaire de statistiques
        """
        priority_counts = {}
        for task in self._queue:
            p = TaskPriority(task.priority).name
            priority_counts[p] = priority_counts.get(p, 0) + 1

        return {
            "queue_size": len(self._queue),
            "processed_count": len(self._processed),
            "by_priority": priority_counts,
            "api_calls_last_minute": {
                api: len([c for c in calls if (datetime.now().timestamp() - c.timestamp()) < 60])
                for api, calls in self._api_calls.items()
            },
        }

    def get_queue_preview(self, limit: int = 10) -> list[dict]:
        """
        Aperçu des prochaines tâches.

        Args:
            limit: Nombre de tâches à afficher

        Returns:
            Liste des prochaines tâches (sans les retirer)
        """
        # Copier et trier
        preview = sorted(self._queue)[:limit]
        return [
            {
                "url": t.url,
                "blog_id": t.blog_id,
                "action": t.action,
                "priority": TaskPriority(t.priority).name,
                "scheduled_at": t.scheduled_at,
            }
            for t in preview
        ]
