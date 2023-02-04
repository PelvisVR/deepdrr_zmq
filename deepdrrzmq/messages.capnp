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
    path @0 :Text;
    worldFromAnatomical @1 :Matrix4x4;
    useThresholding @2 :Bool;
    useCached @3 :Bool;
    saveCache @4 :Bool;
    cacheDir @5 :Text;
#   materials @? :List(Text);
    segmentation @6 :Bool;
#    densityKwargs @? :List(Text);
}

struct DicomLoaderParams { # todo
    path @0 :Text;
    worldFromAnatomical @1 :Matrix4x4;
    useThresholding @2 :Bool;
    useCached @3 :Bool;
    saveCache @4 :Bool;
    cacheDir @5 :Text;
#   materials @? :List(Text);
    segmentation @6 :Bool;
#    densityKwargs @? :List(Text);
}

struct VolumeLoaderParams {
    union {
        nifti @0 :NiftiLoaderParams;
        dicom @1 :DicomLoaderParams;
    }
}

struct ProjectorParams {
    volumes @0 :List(VolumeLoaderParams);
    step @1 :Float32;
    mode @2 :Text;
    spectrum @3 :Text;
    addScatter @4 :Bool;
    scatterNum @5 :UInt32;
    addNoise @6 :Bool;
    photonCount @7 :UInt32;
    threads @8 :UInt32;
    maxBlockIndex @9 :UInt32;
    collectedEnergy @10 :Bool;
    neglog @11 :Bool;
    intensityUpperBound @12 :Float32;
    attenuateOutsideVolume @13 :Bool;
}

struct StatusResponse {
#    success @0 :Bool;
    code @0 :UInt16;
    message @1 :Text;
}

struct ProjectRequest {
    requestId @0 :Text;
    projectorId @1 :Text;
    cameraProjections @2 :List(CameraProjection);
    volumesWorldFromAnatomical @3 :List(Matrix4x4);
}

struct ProjectResponse {
    requestId @0 :Text;
    projectorId @1 :Text;
    status @2 :StatusResponse;
    images @3 :List(Image);
}

struct CreateProjectorRequest {
    projectorId @0 :Text;
    projectorParams @1 :ProjectorParams;
}

struct DeleteProjectorRequest {
    projectorId @0 :Text;
}

struct ServerCommand {
    union {
        createProjector @0 :CreateProjectorRequest;
        deleteProjector @1 :DeleteProjectorRequest;
    }
}