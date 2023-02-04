@0xeaa72c8788903898;

struct Time {
  millis @0 :UInt64;
}

struct Matrix3x3{
  data @0 :List(Float32);
}

struct Matrix4x4 {
  data @0 :List(Float32);
}

struct Image {
  data @0 :Data;
}

struct CameraProjection {
    intrinsic @0 :Matrix3x3;
    extrinsic @1 :Matrix4x4;
}

struct NiftiLoaderParams {
    path @0 :String;
    world_from_anatomical @1 :Matrix4x4;
    use_thresholding @2 :Bool;
    use_cached @3 :Bool;
    save_cache @4 :Bool;
    cache_dir @5 :String;
#   materials @6 :List(String);
    segmentation @7 :Bool;
#    density_kwargs @8 :List(String);
}

struct VolumeLoaderParams {
    union {
        nifti @0 :NiftiLoaderParams;
    }
}

struct ProjectorParams {
    projector_id @0 :String;
    volumes @1 :List(VolumeLoaderParams);
    step @2 :Float32;
    mode @3 :String;
    spectrum @4 :String;
    add_scatter @5 :Bool;
    scatter_num @6 :UInt32;
    add_noise @7 :Bool;
    photon_count @8 :UInt32;
    threads @9 :UInt32;
    max_block_index @10 :UInt32;
    collected_energy @11 :Bool;
    neglog @12 :Bool;
    intensity_upper_bound @13 :Float32;
    attenuate_outside_volume @14 :Bool;
}

struct StatusResponse {
#    success @0 :Bool;
    code @1 :UInt16;
    message @2 :String;
}

struct ProjectRequest {
    request_id @0 :String;
    projector_id @1 :String;
    camera_projections @2 :List(CameraProjection);
    volumes_world_from_anatomical @3 :List(Matrix4x4);
}

struct ProjectResponse {
    request_id @0 :String;
    projector_id @1 :String;
    status @2 :StatusResponse;
    images @3 :List(Image);
}

struct ServerCommand {
    union {
        create_projector @0 :ProjectorParams;
    }
}