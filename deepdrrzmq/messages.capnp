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
    worldFromAnatomical @1 :Matrix4x4;
    useThresholding @2 :Bool;
    useCached @3 :Bool;
    saveCache @4 :Bool;
    cacheDir @5 :String;
#   materials @6 :List(String);
    segmentation @7 :Bool;
#    densityKwargs @8 :List(String);
}

struct VolumeLoaderParams {
    union {
        nifti @0 :NiftiLoaderParams;
    }
}

struct ProjectorParams {
    projectorId @0 :String;
    volumes @1 :List(VolumeLoaderParams);
    step @2 :Float32;
    mode @3 :String;
    spectrum @4 :String;
    addScatter @5 :Bool;
    scatterNum @6 :UInt32;
    addNoise @7 :Bool;
    photonCount @8 :UInt32;
    threads @9 :UInt32;
    maxBlockIndex @10 :UInt32;
    collectedEnergy @11 :Bool;
    neglog @12 :Bool;
    intensityUpperBound @13 :Float32;
    attenuateOutsideVolume @14 :Bool;
}

struct StatusResponse {
#    success @0 :Bool;
    code @1 :UInt16;
    message @2 :String;
}

struct ProjectRequest {
    requestId @0 :String;
    projectorId @1 :String;
    cameraProjections @2 :List(CameraProjection);
    volumesWorldFromAnatomical @3 :List(Matrix4x4);
}

struct ProjectResponse {
    requestId @0 :String;
    projectorId @1 :String;
    status @2 :StatusResponse;
    images @3 :List(Image);
}

struct ServerCommand {
    union {
        createProjector @0 :ProjectorParams;
    }
}