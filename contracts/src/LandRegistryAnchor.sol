// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @title LandRegistryAnchor — public, tamper-evident anchor of off-chain Ugandan land records
/// @notice One transaction per district per batch commits a Merkle root that proves every event
///         in that batch existed at a known time. The on-chain layer never sees PII — only hashes.
/// @dev    Uses keccak256 for on-chain Merkle proofs (gas-cheaper than SHA-256). The backend
///         translates SHA-256 leaves to keccak-equivalents at anchor time. See
///         backend/app/blockchain/anchor_service.py for the bridging logic.
contract LandRegistryAnchor is AccessControl, Pausable {
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");

    struct Anchor {
        bytes32 merkleRoot;
        uint16 districtId;
        uint64 timestamp;
        address registrar;
    }

    mapping(bytes32 => Anchor) public anchors;
    uint256 public totalAnchors;

    event AnchorCommitted(
        bytes32 indexed batchId,
        uint16 indexed districtId,
        bytes32 merkleRoot,
        address indexed registrar,
        uint64 timestamp
    );

    error DuplicateBatch(bytes32 batchId);
    error EmptyRoot();

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REGISTRAR_ROLE, admin);
    }

    function commitBatch(
        uint16 districtId,
        bytes32 batchId,
        bytes32 merkleRoot
    ) external onlyRole(REGISTRAR_ROLE) whenNotPaused {
        if (merkleRoot == bytes32(0)) revert EmptyRoot();
        if (anchors[batchId].timestamp != 0) revert DuplicateBatch(batchId);
        anchors[batchId] = Anchor({
            merkleRoot: merkleRoot,
            districtId: districtId,
            timestamp: uint64(block.timestamp),
            registrar: msg.sender
        });
        unchecked {
            totalAnchors += 1;
        }
        emit AnchorCommitted(batchId, districtId, merkleRoot, msg.sender, uint64(block.timestamp));
    }

    /// @notice Verify that ``leaf`` is included in the batch ``batchId``'s Merkle tree.
    /// @dev    Pair-hashing rule: hash(min(a,b) || max(a,b)) at every level. The backend
    ///         frontend mirror this rule when constructing the proof.
    function verifyProof(
        bytes32 batchId,
        bytes32 leaf,
        bytes32[] calldata proof
    ) external view returns (bool) {
        bytes32 root = anchors[batchId].merkleRoot;
        if (root == bytes32(0)) return false;
        bytes32 computed = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 sibling = proof[i];
            computed = computed <= sibling
                ? keccak256(abi.encodePacked(computed, sibling))
                : keccak256(abi.encodePacked(sibling, computed));
        }
        return computed == root;
    }

    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }
}
