# Controlling an ER-4iA in ROBOGUIDE from Ubuntu (ROS 2 Humble) over Wi-Fi

This guide connects MoveIt 2 on an Ubuntu PC to a virtual FANUC controller
running in ROBOGUIDE on a Windows PC, with both machines on the same Wi-Fi
network. It uses the official [FANUC ROS 2 driver](https://github.com/FANUC-CORPORATION/fanuc_driver)
(`humble` branch) and this package.

```text
┌──────────────────────────┐        Wi-Fi / LAN        ┌──────────────────────────┐
│ Ubuntu 22.04, ROS 2      │  TCP 16001 (RMI)          │ Windows PC               │
│ Humble                   │ ───────────────────────▶  │ ROBOGUIDE (HandlingPRO)  │
│  MoveIt 2 + RViz         │  UDP 60015 (Stream Motion)│  virtual ER-4iA          │
│  fanuc_hardware_interface│ ◀──────────────────────▶  │  controller              │
└──────────────────────────┘                           └──────────────────────────┘
        robot_ip = the Windows PC's Wi-Fi IPv4 address
```

## 1. What you need

| Item | Requirement |
| --- | --- |
| ROBOGUIDE | HandlingPRO (no extra plug-ins needed) |
| Virtual controller | R-30iB Plus / Mate Plus **V9.40P/81+**, R-30iB Mini Plus **V9.40P/77+**, or R-50iA **V10.10P/26+** |
| Controller software options | **J519 Stream Motion** and **R912 Remote Motion**, or **S636 External Control Package** (has both) |
| Ubuntu PC | Ubuntu 22.04, ROS 2 Humble Desktop, MoveIt 2 |
| Network | Both PCs on the same subnet. Peer-to-peer traffic must be allowed (see §7). |

You do **not** need J568 or J570, even though those option names mention ROS 2.

## 2. Create the workcell in ROBOGUIDE (Windows)

1. **File → New Cell** → choose **Create Robot using Robot Creation Wizard**.
2. Choose a controller version that meets the minimum above.
3. Select the robot **ER-4iA** (shown as *LR Mate/4-6D Entry* on R-50iA).
4. On the **software options** page, tick **J519 Stream Motion** and **R912 Remote Motion**
   (or **S636**). You can't add these later without recreating the robot, so check them now.
5. Finish the wizard and let the virtual controller boot.

To confirm the options are installed, open the virtual teach pendant and go to
**MENU → STATUS → Version ID → CONFIG**. Look for *Stream Motion J519* and
*Remote Motion R912*, or *S636*.

## 3. Make the virtual robot reachable from the network

By default, ROBOGUIDE serves the virtual controller on the Windows PC's own
address. Other machines can see it once loopback mode is off:

1. In ROBOGUIDE's options, **untick "Run virtual robots with loopback address"**.
2. Restart the virtual controller (or reopen the workcell).

## 4. Prepare Windows networking

1. Find the Windows PC's Wi-Fi address: run `ipconfig` in Command Prompt and
   note the **IPv4 Address** under *Wireless LAN adapter Wi-Fi*, for example
   `192.168.1.48`. This is your `robot_ip`.
2. Set the Wi-Fi network profile to **Private**
   (Settings → Network & Internet → Wi-Fi → your network).
3. **Firewall.** FANUC's documentation says to disable Windows Firewall so the UDP stream can get
   through. That is the quickest way to test. If you'd rather keep the firewall on, run these
   in an **Administrator PowerShell** to open only what the driver uses:

   ```powershell
   New-NetFirewallRule -DisplayName "FANUC RMI TCP 16001"   -Direction Inbound -Protocol TCP -LocalPort 16001 -Action Allow -Profile Private
   New-NetFirewallRule -DisplayName "FANUC StreamMotion UDP" -Direction Inbound -Protocol UDP -LocalPort 60015 -Action Allow -Profile Private
   New-NetFirewallRule -DisplayName "ICMP ping"             -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -Action Allow -Profile Private
   ```

   If it still won't connect, temporarily turn the firewall off for the Private
   profile to rule it out.
4. Stop the PC from sleeping while you test.

## 5. Put the virtual controller in a state that accepts remote motion

On the ROBOGUIDE virtual teach pendant:

- Set the mode to **AUTO**.
- Set the teach pendant to **OFF** (disabled).
- **RESET** to clear all alarms.

## 6. Build the workspace (Ubuntu)

```bash
sudo apt install git-lfs && git lfs install
mkdir -p ~/fanuc_ws/src && cd ~/fanuc_ws/src
git clone https://github.com/FANUC-CORPORATION/fanuc_description.git
git clone --branch humble --single-branch --recurse-submodules \
    https://github.com/FANUC-CORPORATION/fanuc_driver.git
git clone https://github.com/MithillPrabhu/fanuc_er4ia_moveit_config.git

cd ~/fanuc_ws
source /opt/ros/humble/setup.bash
rosdep update && rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

`--recurse-submodules` is required: the driver builds `sockpp`,
`readerwriterqueue`, `reflect-cpp` and `yaml-cpp` from submodules.

Make sure ROS isn't restricted to localhost:

```bash
unset ROS_LOCALHOST_ONLY        # and remove it from ~/.bashrc if it's set to 1
```

### Test with mock hardware first

```bash
ros2 launch fanuc_er4ia_moveit_config fanuc_er4ia.launch.py
```

RViz opens. Drag the interactive marker, then press **Plan & Execute**. If this
works, MoveIt and the description side are fine.

## 7. Check the network path

Run these from Ubuntu, replacing the IP with your Windows PC's:

```bash
ping -c 4 192.168.1.48            # basic reachability
nc -vz 192.168.1.48 16001         # RMI port must report "succeeded"/"open"
```

If ping fails, the two PCs can't see each other. Common causes:

- **College, office and hotel Wi-Fi often block device-to-device traffic** (client/AP isolation).
  Use a home router, your own access point or a phone hotspot instead, or connect both PCs to a
  switch with an Ethernet cable.
- The PCs are on different subnets, for example 2.4 GHz and 5 GHz networks bridged differently,
  or a guest network.
- The Windows firewall (see §4).

## 8. Connect to ROBOGUIDE and move the robot

```bash
source ~/fanuc_ws/install/setup.bash
ros2 launch fanuc_er4ia_moveit_config fanuc_er4ia.launch.py \
    use_mock:=false robot_ip:=192.168.1.48
```

1. Wait until the log shows that `joint_trajectory_controller` is active. The RViz model should
   match the ROBOGUIDE pose.
2. In RViz, choose the `arm` group, drag the marker, then press **Plan & Execute**. The robot in
   ROBOGUIDE moves.
3. Start slowly: use the MotionPlanning panel's velocity/acceleration scaling (defaults are 10%).

Useful checks while the system is running:

```bash
ros2 control list_controllers             # joint_trajectory_controller [active]
ros2 control list_hardware_components     # FANUC hardware: active
ros2 topic echo /joint_states --once      # live joint angles from ROBOGUIDE
```

**First connection:** if the controller raises **`RMIT-016 Please Cycle Power`**,
restart the virtual controller in ROBOGUIDE, then relaunch the ROS side. The
controller disables Hot Start for Remote Motion automatically.

## 9. Wi-Fi caveats

Stream Motion sends a UDP packet every controller cycle, typically every 8 ms. On Wi-Fi:

- Latency spikes or lost packets can make motion jerky or raise a stream-motion alarm on the
  controller. That's acceptable for ROBOGUIDE experiments.
- To reduce it, put both PCs on 5 GHz close to the router, or use a phone hotspot with nothing
  else connected.
- **For a real robot, use a wired Ethernet link on an isolated port.** FANUC recommends this.
  Don't run real hardware over Wi-Fi.

## 10. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `[FR_HW_Interface]: Failed to create TCP connection` | Can't reach TCP 16001. Check ping/`nc` (§7), loopback setting (§3), firewall (§4). Also appears if **R912** isn't installed. |
| TCP connects but the robot never moves | UDP 60015 is blocked by the firewall, the controller isn't in AUTO with the TP off, or there's an active alarm. Press RESET on the virtual TP. |
| `RMIT-016 Please Cycle Power` | Restart the virtual controller, then relaunch (§8). |
| GPIO configuration error at start-up | Keep the default `gpio_config_path:=config/example_gpio_config_small.yaml`. |
| Connection drops after a long idle period | RMI disconnect timer (default 60 min). On R-30iB Plus set `$RMI_CFG.$DISCNT_TIM`. On R-50iA use MENU → UTILITIES → RMI Setup → Disconnect Time. `0` disables it. |
| Hardware component goes inactive after an alarm | Clear the alarm, then re-activate: `ros2 control set_hardware_component_state <name> inactive` and then `active`. |
| ROBOGUIDE on the same PC under WSL2 | Set WSL2 `networkingMode=mirrored`. NAT mode drops the UDP stream. |

References: [FANUC ROS 2 Driver documentation](https://fanuc-corporation.github.io/fanuc_driver_doc/)
and its ROBOGUIDE, Quick Start and Troubleshooting pages.
