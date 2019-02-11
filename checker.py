import os, glob
import errors
from importlib import reload
reload(errors)
from errors import DesignSpaceError
import ufoProcessor
from ufoProcessor import DesignSpaceProcessor, getUFOVersion, getLayer
from fontParts.fontshell import RFont
from pprint import pprint

class DesignSpaceChecker(object):
    _registeredTags = dict(wght = 'weight', wdth = 'width', slnt = 'slant', opsz = 'optical', ital = 'italic')
    def __init__(self, pathOrObject):
        # check things
        self.errors = []
        if isinstance(pathOrObject, str):
            self.ds = DesignSpaceProcessor()
            if os.path.exists(pathOrObject):
                try:
                    self.ds.read(pathOrObject)
                except:
                    self.errors.append(DesignSpaceError(0,0))
        else:
            self.ds = pathOrObject

    def data_getAxisValues(self, axisName=None):
        # return the minimum / default / maximum for the axis
        # it's possible we ask for an axis that is not in the document.
        if self.ds is None:
            return None
        if axisName is None:
            # get all of them
            axes = {}
            for ad in self.ds.axes:
                axes[ad.name] = (ad.minimum, ad.default, ad.maximum)
            return axes
        for ad in self.ds.axes:
            if ad.name == axisName:
                return ad.minimum, ad.default, ad.maximum
        return None
    
    def hasStructuralErrors(self):
        # check if we have any errors from categories file / axes / sources
        # this does not guarantee there won't be other problems!
        for err in self.errors:
            if err.category in [0,1,2]:
                return True
        return False

    def hasDesignErrors(self):
        # check if there are errors in font data itself, glyphs, fontinfo, kerning
        if self.hasStructuralErrors():
            return -1
        for err in self.errors:
            if err.category in [4,5,6]:
                return True
        return False

    def checkEverything(self):
        if not self.ds:
            return False
        # designspace specific
        self.checkDesignSpaceGeometry()
        self.checkSources()
        self.checkInstances()
        self.checkRules()
        if not self.hasStructuralErrors():
            # font specific
            self.ds.loadFonts()
            self.nf = self.ds.getNeutralFont()
            self.checkKerning()
            self.checkFontInfo()
            self.checkGlyphs()
    
    def checkDesignSpaceGeometry(self):
        # 1.0	no axes defined
        if len(self.ds.axes) == 0:
            self.errors.append(DesignSpaceError(1,0))
        # 1.1	axis missing
        for i, ad in enumerate(self.ds.axes):
            # 1.5	axis name missing
            if ad.name is None:
                axisName = "unnamed_axis_%d" %i
                self.errors.append(DesignSpaceError(1,5), dict(axisName=axisName))
            else:
                axisName = ad.name
            # 1.2	axis maximum missing
            if ad.maximum is None:
                self.errors.append(DesignSpaceError(1,2, dict(axisName=axisName)))
            # 1.3	axis minimum missing
            if ad.minimum is None:
                self.errors.append(DesignSpaceError(1,3, dict(axisName=axisName)))
            # 1.4	axis default missing
            if ad.default is None:
                self.errors.append(DesignSpaceError(1,4, dict(axisName=axisName)))
            # 1,9 minimum and maximum value are the same and not None
            if (ad.minimum == ad.maximum) and ad.minimum != None:
                self.errors.append(DesignSpaceError(1,9, dict(axisName=axisName)))
            # 1,10 default not between minimum and maximum
            if ad.minimum is not None and ad.maximum is not None and ad.default is not None:
                if not ((ad.minimum < ad.default <= ad.maximum) or (ad.minimum <= ad.default < ad.maximum)):
                    self.errors.append(DesignSpaceError(1,10, dict(axisName=axisName)))

            # 1.6	axis tag missing
            if ad.tag is None:
                self.errors.append(DesignSpaceError(1,6, dict(axisName=axisName)))
            # 1.7	axis tag mismatch
            else:
                if ad.tag in self._registeredTags:
                    regName = self._registeredTags[ad.tag]
                    if regName not in axisName.lower():
                        self.errors.append(DesignSpaceError(1,6, dict(axisName=axisName)))
            # 1.8	mapping table has overlaps
            # XX
    
    def checkSources(self):
        axisValues = self.data_getAxisValues()
        # 2,0 no sources defined
        if len(self.ds.sources) == 0:
            self.errors.append(DesignSpaceError(2,0))
        for i, sd in enumerate(self.ds.sources):
            if sd.path is None:
                self.errors.append(DesignSpaceError(2,1, dict(path=sd.path)))
            # 2,1 source UFO missing
            elif not os.path.exists(sd.path):
                self.errors.append(DesignSpaceError(2,1, dict(path=sd.path)))
            else:
                # 2,2 source UFO format too old
                # XX what is too old, what to do with UFOZ
                formatVersion = getUFOVersion(sd.path)
                if formatVersion < 3:
                    self.errors.append(DesignSpaceError(2,2, dict(path=sd.path, version=formatVersion)))
                else:
                    # 2,3 source layer missing
                    if sd.layerName is not None:
                        ufo = RFont(sd.path, showInterface=False)    
                        layerObj = getLayer(ufo, sd.layerName)
                        if layerObj is None:
                            self.errors.append(DesignSpaceError(2,3, dict(path=sd.path, layerName=sd.layerName)))
                if sd.location is None:            
                    # 2,4 source location missing
                    self.errors.append(DesignSpaceError(2,4, dict(path=sd.path)))
                else:
                    for axisName, axisValue in sd.location.items():
                        if type(axisValue) == tuple:
                            axisValues = list(axisValue)
                            self.errors.append(DesignSpaceError(2,10, dict(location=sd.location)))
                        else:
                            if axisName in axisValues:
                                # 2,6 source location has out of bounds value
                                mn, df, mx = axisValues[axisName]
                                if axisValue < mn or axisValue > mx:
                                    self.errors.append(DesignSpaceError(2,6, dict(axisMinimum=mn, axisMaximum=mx, locationValue=axisValue)))
                            else:
                                # 2,5 source location has value for undefined axis
                                self.errors.append(DesignSpaceError(2,5, dict(axisName=axisName)))
        defaultLocation = self.ds.newDefaultLocation()
        defaultCandidates = []
        for i, sd in enumerate(self.ds.sources):
            if sd.location == defaultLocation:
                defaultCandidates.append(sd)
        if len(defaultCandidates) == 0:
            # 2,7 no source on default location
            self.errors.append(DesignSpaceError(2,7))
        elif len(defaultCandidates) > 1:
            # 2,8 multiple sources on default location
            self.errors.append(DesignSpaceError(2,8))
        allLocations = {}
        hasAnisotropicLocation = False
        for i, sd in enumerate(self.ds.sources):
            key = list(sd.location.items())
            key.sort()
            key = tuple(key)
            if key not in allLocations:
                allLocations[key] = []
            allLocations[key].append(sd)
            # if tuple in [type(n) for n in sd.location.values()]:
            #     # 2,10 source location is anisotropic
            #     self.errors.append(DesignSpaceError(2,10))
        for key, items in allLocations.items():
            if len(items) > 1 and items[0].location != defaultLocation:
                # 2,9 multiple sources on location
                self.errors.append(DesignSpaceError(2,9))
    
    def checkInstances(self):
        axisValues = self.data_getAxisValues()
        defaultLocation = self.ds.newDefaultLocation()
        defaultCandidates = []
        if len(self.ds.instances) == 0:
            self.errors.append(DesignSpaceError(3, 10))
        for i, jd in enumerate(self.ds.instances):
            if jd.location is None:            
                # 3,1   instance location missing
                self.errors.append(DesignSpaceError(3,1, dict(path=jd.path)))
            else:
                for axisName, axisValue in jd.location.items():
                    if type(axisValue) == tuple:
                        axisValues = list(axisValue)
                    else:
                        axisValues = [axisValue]
                    for axisValue in axisValues:
                        if axisName in axisValues:
                            # 3,5   instance location requires extrapolation
                            # 3,3   instance location has out of bounds value
                            mn, df, mx = axisValues[axisName]
                            if axisValue < mn or axisValue > mx:
                                self.errors.append(DesignSpaceError(3,3, dict(axisMinimum=mn, axisMaximum=mx, locationValue=axisValue)))
                                self.errors.append(DesignSpaceError(3,5, dict(axisMinimum=mn, axisMaximum=mx, locationValue=axisValue)))
                            else:
                                # 3,2   instance location has value for undefined axis
                                self.errors.append(DesignSpaceError(3,2, dict(axisName=axisName)))

        allLocations = {}
        for i, jd in enumerate(self.ds.instances):
            key = list(jd.location.items())
            key.sort()
            key = tuple(key)
            if key not in allLocations:
                allLocations[key] = []
            allLocations[key].append((i,jd))
        for key, items in allLocations.items():
            # 3,4   multiple sources on location
            if len(items) > 1:
                self.errors.append(DesignSpaceError(3,4, dict(location=items[0][1].location, instances=[a for a,b in items])))
        
        # 3,5   instance location is anisotropic
        for i, jd in enumerate(self.ds.instances):
            # 3,6   missing family name
            if jd.familyName is None:
                self.errors.append(DesignSpaceError(3,6, dict(instance=i)))
            # 3,7   missing style name
            if jd.styleName is None:
                self.errors.append(DesignSpaceError(3,7, dict(instance=i)))
            # 3,8   missing output path
            if jd.path is None:
                self.errors.append(DesignSpaceError(3,8, dict(instance=i)))
        # 3,9   duplicate instances
    
    def checkGlyphs(self):
        # check all glyphs in all fonts
        # need to load the fonts before we can do this
        if not hasattr(self.ds, "collectMastersForGlyph"):
            return
        glyphs = {}
        # 4.7 default glyph is empty
        for fontName, fontObj in self.ds.fonts.items():
            #print("fontObj", fontObj.path)
            for glyphName in fontObj.keys():
                if not glyphName in glyphs:
                    glyphs[glyphName] = []
                glyphs[glyphName].append(fontObj)
        for name in glyphs.keys():
            if name not in self.nf:
                self.errors.append(DesignSpaceError(4,7, dict(glyphName=name)))
            self.checkGlyph(name)


    def checkGlyph(self, glyphName):
        # 4.0 different number of contours in glyph
        # 4.1 different number of components in glyph
        # 4.2 different number of anchors in glyph
        # 4.3 different number of on-curve points on contour
        # 4.4 different number of off-curve points on contour
        # 4.5 curve has wrong type
        # 4.6 non-default glyph is empty
        # 4.8 contour has wrong direction
        items = self.ds.collectMastersForGlyph(glyphName)
        #print(glyphName, len(items))
        #for loc, mg, masters in items:
        #    pprint(masters)
        pass
    
    def checkKerning(self):
        # 5,0 no kerning in source
        # 5,2 kerning group members do not match
        # 5,3 kerning group missing
        # 5,4 kerning pair missing
        #print("checkKerning")
        # 5,1 no kerning in default
        if len(self.nf.kerning) == 0:
            self.errors.append(DesignSpaceError(5,1, dict(fontObj=self.nf)))
        # 5,5 no kerning groups in default
        if len(self.nf.groups) == 0:
            self.errors.append(DesignSpaceError(5,5, dict(fontObj=self.nf)))
        defaultGroupNames = list(self.nf.groups.keys())
        #print("defaultGroupNames", defaultGroupNames)
        for fontName, fontObj in self.ds.fonts.items():
            if fontObj == self.nf:
                continue
            # 5,0 no kerning in source
            #print(fontObj, list(fontObj.kerning.keys()))
            if len(fontObj.kerning.keys()) == 0:
                self.errors.append(DesignSpaceError(5,0, dict(fontObj=self.nf)))
            # 5,6 no kerning groups in source
            if len(fontObj.groups.keys()) == 0:
                self.errors.append(DesignSpaceError(5,6, dict(fontObj=self.nf)))
            for sourceGroupName in fontObj.groups.keys():
                #print("xx", sourceGroupName)
                if not sourceGroupName in defaultGroupNames:
                    # 5,3 kerning group missing
                    self.errors.append(DesignSpaceError(5,3, dict(fontObj=self.nf, groupName=sourceGroupName)))
                else:
                    # check if they have the same members
                    sourceGroupMembers = fontObj.groups[sourceGroupName]
                    defaultGroupMembers = self.nf.groups[sourceGroupName]
                    if sourceGroupMembers != defaultGroupMembers:
                        # 5,2 kerning group members do not match
                        self.errors.append(DesignSpaceError(5,2, dict(fontObj=self.nf, groupName=sourceGroupName)))


    def checkFontInfo(self):
        # check some basic font info values
        # entirely debateable what we should be 
        # 6,3 source font info missing value for xheight
        if self.nf.info.unitsPerEm == None:
            # 6,0 source font info missing value for units per em
            self.errors.append(DesignSpaceError(6,0, dict(fontObj=self.nf)))
        if self.nf.info.ascender == None:
            # 6,1 source font info missing value for ascender
            self.errors.append(DesignSpaceError(6,1, dict(fontObj=self.nf)))
        if self.nf.info.descender == None:
            # 6,2 source font info missing value for descender
            self.errors.append(DesignSpaceError(6,2, dict(fontObj=self.nf)))
        if self.nf.info.descender == None:
            # 6,3 source font info missing value for xheight
            self.errors.append(DesignSpaceError(6,3, dict(fontObj=self.nf)))
        for fontName, fontObj in self.ds.fonts.items():
            if fontObj == self.nf:
                continue
            # 6,4 source font unitsPerEm value different from default unitsPerEm
            if fontObj.info.unitsPerEm != self.nf.info.unitsPerEm:
                self.errors.append(DesignSpaceError(6,4, dict(fontObj=fontObj, fontValue=fontObj.info.unitsPerEm, defaultValue=self.nf.info.unitsPerEm)))

    
    def checkRules(self):
        pass
    

if __name__ == "__main__":
    pass
    # ufoProcessorRoot = "/Users/erik/code/ufoProcessor/Tests"
    # paths = []
    # for name in os.listdir(ufoProcessorRoot):
    #     p = os.path.join(ufoProcessorRoot, name)
    #     if os.path.isdir(p):
    #         p2 = os.path.join(p, "*.designspace")
    #         paths += glob.glob(p2)
    # for p in paths:
    #     dc = DesignSpaceChecker(p)
    #     dc.checkEverything()
    #     if dc.errors:
    #         print("\n")
    #         print(os.path.basename(p))
    #         # search for specific errors!
    #         for n in dc.errors:
    #             print("\t" + str(n))
    #         for n in dc.errors:
    #             if n.category == 3:
    #                 print("\t -- "+str(n))



