#!/bin/bash
# Disable skill monitoring and restore pre-monitoring state

echo "Disabling skill monitoring..."

# Option 1: Keep data, just disable hooks
disable_hooks_only() {
    echo "Removing hooks from settings (keeping data)..."
    git checkout 0c8ca2d -- .claude/settings.local.json
    echo "SUCCESS: Hooks disabled. Data preserved in memory/"
    echo "To re-enable: git checkout main -- .claude/settings.local.json"
}

# Option 2: Full rollback to pre-monitoring state
full_rollback() {
    echo "Full rollback to pre-monitoring state..."
    git checkout 0c8ca2d
    echo "SUCCESS: Reverted to commit 0c8ca2d (pre-monitoring)"
    echo "All monitoring code and data removed"
}

# Option 3: Keep everything, just set enabled=false in config
soft_disable() {
    echo "Soft disable (set config enabled=false)..."
    sed -i 's/enabled: true/enabled: false/' config.yml
    echo "SUCCESS: Monitoring disabled in config.yml"
    echo "Hooks still run but do nothing"
}

# Show options
echo ""
echo "Select rollback option:"
echo "  1) Disable hooks only (keep data)"
echo "  2) Full rollback (remove all monitoring)"
echo "  3) Soft disable (set config enabled=false)"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1) disable_hooks_only ;;
    2) full_rollback ;;
    3) soft_disable ;;
    *) echo "Invalid choice. Exiting." ;;
esac
