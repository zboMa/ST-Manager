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
    
    // 如果 expandedFolders 是 null，表示不控制展开状态，所有节点都可见
    // 如果 expandedFolders 是对象（即使是空对象），则根据展开状态控制可见性
    const useExpandedControl = expandedFolders !== null;
    const expandedMap = expandedFolders || {};

    // 构建路径到文件夹的映射，用于快速查找子节点
    const pathMap = {};
    folders.forEach(folder => {
        pathMap[folder.path] = folder;
    });

    return folders.map(folder => {
        let isVisible = true;

        // 仅在明确提供 expandedFolders（非 null）时，才根据父级展开状态计算可见性
        if (useExpandedControl && folder.level > 0) {
            const parts = folder.path.split('/');
            
            // 检查所有父级路径是否都已展开
            // 对于 level 1 的节点（如 "test1"），parts = ["test1"]，需要检查根节点（空字符串）
            // 对于 level > 1 的节点（如 "test1/test11"），parts = ["test1", "test11"]，需要检查所有父级路径
            
            // 构建所有需要检查的父级路径
            const parentPaths = [];
            let currentPath = '';
            
            // 对于 level 1 的节点，直接父级是根节点（空字符串）
            if (folder.level === 1) {
                parentPaths.push('');
            } else {
                // 对于 level > 1 的节点，需要检查所有父级路径（包括根节点）
                parentPaths.push(''); // 根节点
                for (let i = 0; i < parts.length - 1; i++) {
                    currentPath = i === 0 ? parts[i] : `${currentPath}/${parts[i]}`;
                    parentPaths.push(currentPath);
                }
            }
            
            // 检查所有父级路径是否都已展开
            for (const parentPath of parentPaths) {
                if (!expandedMap[parentPath]) {
                    isVisible = false;
                    break;
                }
            }
        }

        // 判断是否有子节点（查找是否有 level + 1 且 path 以当前 path + '/' 开头的节点）
        const hasChildren = folders.some(f => 
            f.level === folder.level + 1 && 
            f.path.startsWith(folder.path === '' ? '' : folder.path + '/')
        );

        return {
            ...folder,
            visible: isVisible,
            expanded: !!expandedMap[folder.path],
            hasChildren: hasChildren
        };
    });
}

