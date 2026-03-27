# AGENTS.md

## Назначение
Этот репозиторий обслуживает MCP-сервер проекта `mcp_server`.
Агент должен работать автономно, без лишних вопросов пользователю, но с минимальными и проверяемыми изменениями.

## Базовый контекст
- project_root: `/a0/usr/projects/mcp_server`
- source_dir: `/a0/usr/projects/mcp_server/src/mcp_server`
- runtime_dir: `/a0/usr/projects/mcp_server/.runtime`
- service_name: `mcp-server`
- local_base: `http://127.0.0.1:8000`
- health: `http://127.0.0.1:8000/health`
- ready: `http://127.0.0.1:8000/ready`
- main_log: `/a0/usr/projects/mcp_server/server.log`

## Обязательный порядок работы
1. Сначала вызвать `start_work_session`.
2. Затем вызвать `get_task_playbook` с подходящим `task_type` (`debug`, `edit`, `deploy`, `ops`, `general`).
3. Перед любыми изменениями сделать быструю проверку состояния:
   - `health_check`
   - `ready_check`
   - `mcp_self_test` при необходимости
4. Для диагностики использовать узкие инструменты, а не shell по умолчанию:
   - `diagnose_service`
   - `service_health_bundle`
   - `journal_grep`
   - `top_processes`
   - `process_check`
   - `diagnose_port`
   - `port_check_local`
5. Для поиска по проекту использовать:
   - `find_files`
   - `grep_file`
   - `read_file`
   - `stat_path`
   - `list_tree`
   - `read_env_file`
   - `read_json_file`
6. Перед правкой важных файлов по возможности делать резервную копию через `backup_file`.
7. Для изменения файлов предпочитать узкие actions:
   - `replace_in_file`
   - `write_file`
   - `append_file`
   - `copy_path`
   - `move_path`
   - `remove_path`
   - `chmod_path`
   - `chown_path`
   - `mkdir_p`
8. Для управления сервисом предпочитать:
   - `service_start`
   - `service_stop`
   - `service_reload`
   - `service_restart_and_wait`
   - `service_unit_exists`
9. Для Docker предпочитать:
   - `docker_ps`
   - `docker_logs`
   - `docker_inspect`
   - `docker_restart`
   - `docker_exec`
10. После любых изменений обязательно повторно проверить:
   - `health_check`
   - `ready_check`
   - при необходимости `mcp_self_test`

## Жёсткие правила
- Не начинать работу с `run_command`, если есть подходящий узкий tool.
- Не править исходники через `sed -i`, `perl -0pi`, `python -c` patch-in-place, если ту же задачу можно сделать через `replace_in_file`, `write_file`, `append_file`, `copy_path`, `move_path`.
- Не делать массовые и непрозрачные патчи без необходимости.
- Делать изменения маленькими шагами и сразу проверять результат.
- Если нужно редактировать код, сначала прочитать файл, потом менять, потом верифицировать.
- Если задача про сервис, сначала диагностировать, потом менять состояние, потом перепроверять.
- `run_command` использовать только как fallback, когда нет подходящего специализированного инструмента.

## Предпочтительные сценарии
### Debug
1. `health_check`
2. `ready_check`
3. `diagnose_service`
4. `journal_grep` или `tail_file`
5. только потом правки или рестарт
6. повторная проверка

### Edit
1. `find_files` / `grep_file`
2. `read_file`
3. `backup_file`
4. `replace_in_file` или `write_file`
5. `service_reload` или `service_restart_and_wait` при необходимости
6. `health_check` / `ready_check`

### Deploy/Ops
1. `service_health_bundle`
2. `project_quick_facts`
3. необходимые файловые изменения узкими tools
4. `service_restart_and_wait`
5. `mcp_self_test`

## Цель
Этот MCP должен использоваться как основной operational interface. Агент должен вести себя как аккуратный программист-сисадмин: сначала понять состояние, потом внести минимальное изменение, потом немедленно проверить результат.