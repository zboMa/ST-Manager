/**
 * static/js/utils/folderTree.js
 * 通用文件夹树构建工具
 *
 * 输入后端返回的 allFoldersList（每项包含 path / name / level），
 * 根据可选的 expandedFolders 映射，计算出：
 * - visible: 是否在当前展开状态下应该显示
 * - expanded: 当前节点是否展开
 *
 * 如果未提供 expandedFolders，则默认所有节点都可见，expanded=false，
 * 适用于弹窗等简单选择场景。
 */

export function buildFolderTree(list, expandedFolders = null) {
    const folders = Array.isArray(list) ? list : [];
    const expandedMap = expandedFolders || {};

    return folders.map(folder => {
        let isVisible = true;

        // 仅在提供 expandedFolders 时，才根据父级展开状态计算可见性
        if (expandedFolders && folder.level > 0) {
            const parts = folder.path.split('/');
            let currentPath = '';

            for (let i = 0; i < parts.length - 1; i++) {
                currentPath = i === 0 ? parts[i] : `${currentPath}/${parts[i]}`;
                if (!expandedMap[currentPath]) {
                    isVisible = false;
                    break;
                }
            }
        }

        return {
            ...folder,
            visible: isVisible,
            expanded: !!expandedMap[folder.path]
        };
    });
}

