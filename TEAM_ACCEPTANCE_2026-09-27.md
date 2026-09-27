# CSC4801 Team Zzz 项目说明与验收报告

日期：2026-09-27  
项目：TalentMatch / CSC4801_TeamZzz  
用途：给组员快速理解项目、分工复核、后续课程验收和展示准备。

在线演示：https://csc4801.wushenyu.com

GitHub：https://github.com/shenyuwu100-netizen/CSC4801_TeamZzz

在线演示使用独立的合成数据环境，每天自动重置；请不要输入真实个人信息。正式课程交付仍以 GitHub 固定 commit 与 Docker 可复现流程为准。

## 1. 这个项目在干什么

这是一个浏览器端可运行的招聘与候选人匹配平台。

系统只有两种角色：

- Candidate（候选人）
- Employer（雇主）

Candidate 可以：

1. 注册、登录和退出。
2. 编辑自己的姓名、技术技能和私有纯文本简历。
3. 浏览全部岗位。
4. 根据课程规定的确定性技能匹配算法查看岗位匹配分数。
5. 对岗位提交申请。
6. 查看自己的申请状态。
7. 当申请进入 Interviewing 状态后，预约该雇主提供的未来 30 分钟面试时段。
8. 已被其他候选人预约的时段不会再显示。

Employer 可以：

1. 注册、登录和退出。
2. 编辑公司资料。
3. 创建、修改和删除自己的岗位。
4. 查看自己岗位的申请人。
5. 使用与 Candidate 完全相同的匹配算法排序申请人。
6. 把申请状态更新为 Pending / Interviewing / Rejected / Accepted。
7. 创建未来的 30 分钟面试时段。
8. 面试时段属于 Employer，可被该 Employer 不同岗位的 Interviewing 申请预约。
9. 已预约时段不能删除；有申请或时段依赖的岗位不能直接删除。

## 2. 核心业务流程

### Candidate 流程

注册 Candidate -> 登录 -> 填技能/简历 -> 查看推荐岗位 -> 申请岗位 -> Employer 更新状态 -> Interviewing -> 选择该 Employer 的空闲时段 -> 完成预约。

### Employer 流程

注册 Employer -> 登录 -> 填公司资料 -> 创建岗位 -> 查看申请人 -> 根据匹配分数查看排序 -> 修改申请状态 -> 创建 30 分钟面试可用时段 -> 查看 Candidate 的预约结果。

## 3. 匹配算法

课程要求的核心匹配分数是确定性的，不依赖 LLM。

设：

- C = Candidate 技能集合
- R = Job required skills 集合

规则：

- 如果 R 为空，score = 100
- 否则 score = floor(100 * |C ∩ R| / |R|)

实现中会：

- 去掉首尾空白；
- 以逗号、分号或换行拆分技能；
- 使用 lowercase 做大小写归一；
- 去除重复技能；
- Candidate 和 Employer 两端共用同一套评分函数。

排序规则也是确定性的：

- Candidate 端：匹配分数降序 -> 岗位标题不区分大小写排序 -> job ID。
- Employer 端：匹配分数降序 -> Candidate display name 不区分大小写排序 -> candidate ID。

## 4. 面试预约规则

这是本轮重点修正的地方。

课程规范要求：Candidate 的 Interviewing 申请可以预约“该申请对应 Employer”的可用面试时段，不要求时段必须来自同一个 job。

因此现在：

- Employer 创建时段时仍选择一个 source job，用于记录来源和删除依赖。
- Candidate 能看到同一 Employer 旗下所有未来、未预约的时段。
- Candidate 只能预约自己申请对应 Employer 的时段。
- application 必须处于 Interviewing。
- 一个 application 最多一个 booking。
- 一个 slot 最多一个 booking。
- 多个 Candidate 同时抢同一个 slot 时，数据库事务保证只有一个成功；另一个返回 409 / Slot already booked。

## 5. 安全与权限

当前实现包含：

- 密码使用 Werkzeug scrypt 哈希，不明文保存。
- 登录后服务端重新读取用户角色。
- Candidate 不能读取或修改其他 Candidate 的简历/申请。
- Employer 不能读取、修改或删除其他 Employer 的岗位、申请人和时段。
- SQL 使用参数绑定，不拼接用户输入。
- Jinja 默认转义用户内容，防止基本 XSS。
- 操作不存在对象时返回 404。
- 已登录但无权访问对象时返回 403。
- 合法对象但业务输入错误时返回 400。
- 预约/删除冲突使用事务和数据库约束处理。

## 6. 技术栈

- Python 3.12
- Flask
- Jinja
- SQLite
- Werkzeug
- pytest
- Waitress
- Docker
- GitHub Actions

没有 Node.js、外部数据库、付费 API 或 LLM 依赖。

## 7. 主要代码位置

- `recruiting/auth.py`：注册、登录、退出、角色鉴权。
- `recruiting/candidate.py`：Candidate 页面、申请、预约。
- `recruiting/employer.py`：Employer 公司、岗位、申请人、时段。
- `recruiting/matching.py`：唯一的技能归一和匹配算法。
- `recruiting/services.py`：预约、删除、状态等关键业务规则。
- `recruiting/db.py`：SQLite 连接和事务。
- `recruiting/schema.sql`：数据库表和唯一约束。
- `recruiting/seed.py`：确定性的演示数据。
- `tests/unit/`：课程 requirement 对应的单元测试和回归测试。
- `SPEC.md`：完整实现规范。
- `README.md`：项目总览和 requirement-test 映射。
- `INSTALL.md`：安装、运行、测试、Docker。
- `REQUIREMENTS.md`：当前课程 Final Project 的规范副本。

## 8. 本轮升级解决了什么

在原先可运行版本上又修正了以下边界：

1. **跨岗位预约**
   - 原来错误要求 application 和 slot 的 job 相同。
   - 现在严格按课程要求，只要求 Employer 相同。

2. **并发删除**
   - 原来检查依赖和删除之间存在写入竞争窗口。
   - 现在岗位/时段删除在 BEGIN IMMEDIATE 事务内完成检查和删除。

3. **技能 lowercase**
   - 原来用了 Unicode casefold。
   - 现在严格使用课程要求的 lowercase，避免如 Straße / STRASSE 被错误合并。

4. **403 / 404 / 400 顺序**
   - 先判断对象是否存在、是否有权限，再判断业务输入是否合法。
   - 避免非法输入掩盖越权访问。

5. **Docker CI**
   - 不只 build 镜像。
   - CI 还会启动容器、seed、在容器中跑测试并检查 HTTP health。

6. **回归测试**
   - 新增 `tests/unit/test_contract_regressions.py`，专门覆盖上述课程规范边界。

## 9. 当前验收结果

2026-09-27 最终复核：

### 本机

- Contract regression：14 / 14 passed
- 其余 auth/matching/security/workflow：17 / 17 passed
- scheduling：6 / 6 passed
- deployment demo account：2 / 2 passed
- 合计：**39 / 39 passed**
- `git diff --check`：通过

### Docker

- Docker build：通过
- `flask --app recruiting reset-seed`：通过
- `/healthz`：返回 `{"ok":true}`
- Contract regression：14 / 14 passed
- 其余 auth/matching/security/workflow：17 / 17 passed
- scheduling：6 / 6 passed
- deployment demo account：2 / 2 passed
- 合计：**39 / 39 passed**

### 在线演示

- `https://csc4801.wushenyu.com`：公网 HTTPS 访问正常。
- `http://csc4801.wushenyu.com`：308 跳转 HTTPS。
- 公网容器只绑定 `127.0.0.1:18084`，外部入口仅通过 Cloudflare Tunnel。
- demo 数据库与本地开发/测试数据库隔离。
- 容器重启会自动 `reset-seed`，Windows 计划任务每天 04:00 再执行一次确定性重置。
- demo session cookie 使用 `Secure + HttpOnly + SameSite=Lax`。
- deployment-only 固定 demo 账号由未跟踪的 `.env` 提供，reset/restart 后自动恢复，真实账号配置不会提交到 GitHub。

### 课程规范

当前仓库 `REQUIREMENTS.md` 与 Blackboard 最新 `final_project_2995033_1.zip` 中的版本内容一致（换行格式不同，不影响文本内容）。

## 10. 如何自己验收

### 本地

```bash
python -m pip install -r requirements.txt
flask --app recruiting reset-seed
python -m pytest -q
python -m recruiting
```

浏览器打开：

`http://127.0.0.1:8080`

### Docker

```bash
docker build -t csc4801-teamzzz .
docker run -d --name csc4801-teamzzz -p 127.0.0.1:8080:8080 csc4801-teamzzz
docker exec csc4801-teamzzz flask --app recruiting reset-seed
docker exec csc4801-teamzzz python -m pytest -q
```

健康检查：

```text
http://127.0.0.1:8080/healthz
```

## 11. 组员现在需要做什么

项目本体已经达到当前课程要求下的可验收状态，但每个组员都应该至少完成下面几件事：

- [ ] 能说清楚 Candidate 和 Employer 各自能做什么。
- [ ] 能解释技能匹配公式以及为什么是确定性的。
- [ ] 能解释为什么面试 slot 是 Employer 级可用，而不是必须同 job。
- [ ] 能解释 `BEGIN IMMEDIATE` 和 UNIQUE 约束为什么能防止两个人抢同一 slot 都成功。
- [ ] 能找到 Candidate / Employer / matching / services / schema 的代码位置。
- [ ] 自己跑一次 `python -m pytest -q`。
- [ ] 自己用 Candidate 和 Employer demo account 走一遍核心流程。
- [ ] 熟悉 README、SPEC、INSTALL。
- [ ] Week 12 跨组审计时知道 GitHub Issues / audit labels 怎么用。
- [ ] Presentation 前每个人都能独立讲一个模块，不要只有一个人懂代码。

## 12. 后续课程任务

当前完成的是“项目实现 + 当前规范验收”。

后续仍要做：

1. 按课程时间线冻结正式 graded commit。
2. 提交永久 40 位 GitHub commit URL。
3. Week 12 参与 cross-team bug audit。
4. 对有效 bug 做修复并补 regression test。
5. 更新最终文档和 graded commit。
6. Week 13-14 准备 presentation / demo。

## 13. 当前已知非必做功能

以下没有实现，但不影响当前 mandatory requirements：

- PDF resume upload/extraction。
- FP-MATCH-2 optional LLM explanation。

项目故意保持不依赖外部 AI 服务，保证助教可以从 clean checkout 直接本地或 Docker 运行。

## 14. 组员验收结论

当前版本可以作为 Team Zzz 后续协作、跨组审计和 presentation 准备的基线。

核心功能、课程规定的匹配逻辑、权限边界、预约并发、Docker 运行和测试流程均已通过可重复验证。

后续任何修改都应同时更新相应测试和文档，并在提交前重新跑完整测试。
