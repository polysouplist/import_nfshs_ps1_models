#-*- coding:utf-8 -*-

# Blender Need for Speed High Stakes (1999) PS1 importer Add-on
# Add-on developed by PolySoupList


## TO DO
"""
"""


bl_info = {
    "name": "Import Need for Speed High Stakes 1999 PS1 models format (.geo)",
    "description": "Import meshes files from Need for Speed High Stakes 1999 PS1",
    "author": "PolySoupList",
    "version": (0, 0, 3),
    "blender": (3, 6, 23),
    "location": "File > Import > Need for Speed High Stakes 1999 PS1 (.geo)",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Import-Export"}


import bpy
from bpy.types import (
	Operator,
	OperatorFileListElement
)
from bpy.props import (
	StringProperty,
	BoolProperty,
	EnumProperty,
	CollectionProperty
)
from bpy_extras.io_utils import (
	ImportHelper,
	orientation_helper,
	axis_conversion,
)
import bmesh
import math
import os
import time
import struct
from pathlib import Path


def main(context, file_path, is_traffic, clear_scene):
	if bpy.ops.object.mode_set.poll():
		bpy.ops.object.mode_set(mode='OBJECT')
	
	if clear_scene == True:
		print("Clearing scene...")
		clearScene(context)
	
	start_time = time.time()
	
	main_collection_name = os.path.basename(file_path)
	main_collection = bpy.data.collections.new(main_collection_name)
	bpy.context.scene.collection.children.link(main_collection)
	
	print("Importing file %s" % os.path.basename(file_path))
	
	with open(file_path, 'rb') as f:
		f.seek(0x24C)
		
		for partIdx in range(57):
			vertices = []
			normal_data = []
			faces = []
			loop_uvs = []
			face_material_indices = []
			used_texture_ids = set()
			
			has_some_normal_data = False
			
			geoPartName = get_geoPartNames(partIdx)
			#print(f"name: {geoPartName}")
			
			numVertex = struct.unpack('<H', f.read(2))[0]
			#print(f"numVertex: {numVertex}")
			
			numFacet = struct.unpack('<H', f.read(2))[0]
			#print(f"numFacet: {numFacet}")
			
			translation = struct.unpack('<iii', f.read(12))
			translation = [-translation[0]/0x7FFF, -translation[2]/0x7FFF, translation[1]/0x7FFF]
			#print(f"translation: {translation}")
			
			if partIdx == 39:
				translation[0] -= -0x7AE/0x7FFF
			elif partIdx == 40:
				translation[0] += -0x7AE/0x7FFF
			
			unknown = f.read(12)
			
			for i in range (numVertex):
				vertex = struct.unpack('<hhh', f.read(6))
				vertex = [-vertex[0]/0x7F, vertex[1]/0x7F, vertex[2]/0x7F]
				vertices.append ((vertex[0], vertex[1], vertex[2]))
				#print(f"vertex: {vertex[0], vertex[1], vertex[2]}")
			if numVertex % 2 == 1: #Data offset after positions, happens when numVertex is odd.
				padding = f.read(0x2)
			
			if is_traffic == False:
				if get_R3DCar_ObjectInfo(partIdx)[1] & 1 != 0:
					has_some_normal_data = True
					for i in range (numVertex):
						Nvertex = struct.unpack('<hhh', f.read(6))
						Nvertex = [-Nvertex[0]/0x7F, Nvertex[1]/0x7F, Nvertex[2]/0x7F]
						normal_data.append ((Nvertex[0], Nvertex[1], Nvertex[2]))
						#print(f"Nvertex: {Nvertex[0], Nvertex[1], Nvertex[2]}")
					if numVertex % 2 == 1: #Data offset after positions, happens when numVertex is odd.
						padding = f.read(0x2)
			
			for i in range(numFacet):
				flag = struct.unpack('<h', f.read(2))[0]
				#print(f"flag: {flag}")
				textureIndex = struct.unpack('<B', f.read(1))[0]
				#print(f"textureIndex: {textureIndex}")
				vertexId0 = struct.unpack('<B', f.read(1))[0]
				vertexId1 = struct.unpack('<B', f.read(1))[0]
				vertexId2 = struct.unpack('<B', f.read(1))[0]
				#print(f"face: {vertexId0, vertexId1, vertexId2}")
				uv0 = struct.unpack('<BB', f.read(2))
				uv0 = [uv0[0]/0xFF, -uv0[1]/0xFF + 1.0]
				uv1 = struct.unpack('<BB', f.read(2))
				uv1 = [uv1[0]/0xFF, -uv1[1]/0xFF + 1.0]
				uv2 = struct.unpack('<BB', f.read(2))
				uv2 = [uv2[0]/0xFF, -uv2[1]/0xFF + 1.0]
				#print(f"uv: {uv0, uv1, uv2}")
			
				faces.append((vertexId2, vertexId1, vertexId0))
				loop_uvs.extend([uv2, uv1, uv0])
				face_material_indices.append(textureIndex)
				used_texture_ids.add(textureIndex)
				
			if numVertex > 0:
				#==================================================================================================
				#Building Mesh
				#==================================================================================================
				me_ob = bpy.data.meshes.new(geoPartName)
				#obj = bpy.data.objects.new(geoPartName, me_ob)
				me_ob.from_pydata(vertices, [], faces)
				
				values = [True] * len(me_ob.polygons)
				me_ob.polygons.foreach_set("use_smooth", values)
				
				if has_some_normal_data:
					me_ob.validate(clean_customdata=False)
					me_ob.normals_split_custom_set_from_vertices(normal_data)
					me_ob.use_auto_smooth = True
				else:
					me_ob.calc_normals()
				
				if loop_uvs:
					uv_layer = me_ob.uv_layers.new(name="UVMap")
					uv_layer.data.foreach_set("uv", [coord for uv in loop_uvs for coord in uv])
				
				# ------------------- Create Materials -------------------
				sorted_tex_ids = sorted(used_texture_ids)
				tex_id_to_mat_index = {tex_id: idx for idx, tex_id in enumerate(sorted_tex_ids)}
				
				for tex_id in sorted_tex_ids:
					material_name = f"{tex_id}"
					mat = bpy.data.materials.get(material_name)
					if mat == None:
						mat = bpy.data.materials.new(material_name)
						mat.use_nodes = True
						mat.name = material_name
					#me_ob.materials.append(bpy.data.materials.get(material_name))
				
					bsdf = mat.node_tree.nodes["Principled BSDF"]
					bsdf.inputs[0].default_value = (
						(tex_id * 17 % 23) / 23,
						(tex_id * 31 % 29) / 29,
						(tex_id * 47 % 37) / 37,
						1.0
					)
				
					if mat.name not in me_ob.materials:
						me_ob.materials.append(mat)
				
					for face_idx, tex_id in enumerate(face_material_indices):
						blender_mat_index = tex_id_to_mat_index.get(tex_id, 0)
						me_ob.polygons[face_idx].material_index = blender_mat_index
				
				obj = bpy.data.objects.new(geoPartName, me_ob)
				
				# Link to scene
				#bpy.context.collection.objects.link(obj)
				main_collection.objects.link(obj)
				bpy.context.view_layer.objects.active = obj
				
				#empty = bpy.data.objects.new(name="Empty", object_data=None)
				#bpy.context.collection.objects.link(empty)
				
				obj.location = (translation)
				obj.rotation_euler = (math.radians(90), 0, 0)
				
				#obj.parent = empty
	
	print("Finished")
	elapsed_time = time.time() - start_time
	print("Elapsed time: %.4fs" % elapsed_time)
	return {'FINISHED'}


def get_R3DCar_ObjectInfo(partIdx):
    R3DCar_ObjectInfo = {0: [0x00, 0x49, 0x00, 0x01, 0x00, 0x00],
                         1: [0x00, 0x00, 0x00, 0x00, 0x01, 0x00],
                         2: [0x20, 0x02, 0x01, 0x01, 0x00, 0x00],
                         3: [0x30, 0x00, 0x01, 0x01, 0x00, 0x00],
                         4: [0xF8, 0x00, 0x00, 0x00, 0x01, 0x00],
                         5: [0xF0, 0x08, 0x0A, 0x0A, 0x00, 0x00],
                         6: [0xE0, 0x00, 0x0C, 0x00, 0x00, 0x00],
                         7: [0xE0, 0x00, 0x00, 0x0C, 0x00, 0x00],
                         8: [0xEC, 0x89, 0x0B, 0x0B, 0x00, 0x0B],
                         9: [0xF0, 0x88, 0x0B, 0x0B, 0x00, 0x0B],
                         10: [0xEC, 0x89, 0x0C, 0x0C, 0x00, 0x0C],
                         11: [0xF0, 0x88, 0x0C, 0x0C, 0x00, 0x0C],
                         12: [0xE8, 0x00, 0x01, 0x00, 0x00, 0x00],
                         13: [0xE8, 0x00, 0x00, 0x01, 0x00, 0x00],
                         14: [0xD4, 0x00, 0x11, 0x00, 0x00, 0x00],
                         15: [0xD4, 0x00, 0x11, 0x00, 0x00, 0x00],
                         16: [0xE1, 0x08, 0x01, 0x00, 0x00, 0x00],
                         17: [0xE1, 0x08, 0x00, 0x01, 0x00, 0x00],
                         18: [0xD4, 0x00, 0x12, 0x12, 0x12, 0x00],
                         19: [0xE2, 0x00, 0x01, 0x00, 0x00, 0x00],
                         20: [0xE2, 0x00, 0x00, 0x01, 0x00, 0x00],
                         21: [0xD4, 0x00, 0x13, 0x13, 0x13, 0x00],
                         22: [0xE2, 0x18, 0x0F, 0x10, 0x00, 0x00],
                         23: [0xE2, 0x08, 0x00, 0x01, 0x00, 0x00],
                         24: [0xD4, 0x10, 0x14, 0x14, 0x14, 0x00],
                         25: [0xE2, 0x18, 0x0F, 0x10, 0x00, 0x00],
                         26: [0xE2, 0x08, 0x00, 0x01, 0x00, 0x00],
                         27: [0xD4, 0x10, 0x15, 0x15, 0x15, 0x00],
                         28: [0xE8, 0x08, 0x01, 0x00, 0x00, 0x00],
                         29: [0xE8, 0x08, 0x00, 0x01, 0x00, 0x00],
                         30: [0xD4, 0x00, 0x16, 0x16, 0x16, 0x00],
                         31: [0xD8, 0x00, 0x01, 0x01, 0x00, 0x00],
                         32: [0xF4, 0x00, 0x0D, 0x00, 0x00, 0x00],
                         33: [0xF4, 0x00, 0x0E, 0x00, 0x00, 0x00],
                         34: [0xD4, 0x00, 0x11, 0x00, 0x00, 0x00],
                         35: [0x30, 0x00, 0x02, 0x01, 0x00, 0x00],
                         36: [0x28, 0x02, 0x03, 0x00, 0x00, 0x03],
                         37: [0x28, 0x02, 0x03, 0x00, 0x00, 0x03],
                         38: [0x26, 0x02, 0x04, 0x00, 0x00, 0x00],
                         39: [0x24, 0x02, 0x04, 0x00, 0x00, 0x04],
                         40: [0x24, 0x02, 0x04, 0x00, 0x00, 0x04],
                         41: [0x00, 0x49, 0x01, 0x00, 0x00, 0x01],
                         42: [0x00, 0x49, 0x01, 0x00, 0x00, 0x01],
                         43: [0xF0, 0x80, 0x05, 0x00, 0x00, 0x05],
                         44: [0xF0, 0x80, 0x06, 0x00, 0x00, 0x06],
                         45: [0xE8, 0x89, 0x07, 0x07, 0x00, 0x07],
                         46: [0xE8, 0x89, 0x08, 0x08, 0x00, 0x08],
                         47: [0x1F, 0x00, 0x01, 0x01, 0x00, 0x00],
                         48: [0x1F, 0x00, 0x01, 0x01, 0x00, 0x00],
                         49: [0x20, 0x00, 0x01, 0x00, 0x00, 0x00],
                         50: [0x20, 0x00, 0x01, 0x00, 0x00, 0x00],
                         51: [0x20, 0x00, 0x09, 0x01, 0x00, 0x00],
                         52: [0x20, 0x00, 0x09, 0x01, 0x00, 0x00],
                         53: [0x20, 0x00, 0x01, 0x00, 0x00, 0x00],
                         54: [0x20, 0x00, 0x01, 0x00, 0x00, 0x00],
                         55: [0x20, 0x00, 0x09, 0x01, 0x00, 0x00],
                         56: [0x20, 0x00, 0x09, 0x01, 0x00, 0x00]}
    
    return R3DCar_ObjectInfo[partIdx]


def get_geoPartNames(partIdx):
    geoPartNames = {0: "Body Medium",
                    1: "Body Low",
                    2: "Body Undertray",
                    3: "Wheel Wells",
                    4: "Wheel Squares (unknown LOD)",
                    5: "Wheel Squares (A little bigger)",
                    6: "Unknown Invisible??",
                    7: "Unknown Invisible??",
                    8: "Spoiler Original",
                    9: "Spoiler Uprights",
                    10: "Spoiler Upgraded",
                    11: "Spoiler Upgraded Uprights ",
                    12: "Fog Lights and Rear bumper Top",
                    13: "Fog Lights and Rear bumper TopR",
                    14: "Wing Mirror Attachment Points",
                    15: "Wheel Attachment Points",
                    16: "Brake Light Quads",
                    17: "Unknown Invisible",
                    18: "Unknown Rear Light tris",
                    19: "Rear Inner Light Quads",
                    20: "Rear Inner Light Quads rotated",
                    21: "Rear Inner Light Tris",
                    22: "Front Light quads",
                    23: "Bigger Front Light quads",
                    24: "Front Light triangles",
                    25: "Rear Main Light Quads",
                    26: "Rear Main Light Quads dup",
                    27: "Rear Main Light Tris",
                    28: "Unknown Invisible",
                    29: "Unknown Invisible",
                    30: "Front Headlight light Pos",
                    31: "Logo and Rear Numberplate",
                    32: "Exhaust Tips",
                    33: "Low LOD Exhaust Tips",
                    34: "Mid Body F/R Triangles",
                    35: "Interior Cutoff + Driver Pos",
                    36: "Unknown Invisible",
                    37: "Unknown Invisible",
                    38: "Unknown Invisible",
                    39: "Unknown Invisible",
                    40: "Unknown Invisible",
                    41: "Right Body High",
                    42: "Left Body High",
                    43: "Right Wing Mirror",
                    44: "Left Wing Mirror",
                    45: "Front Right Light Bucket",
                    46: "Front Left Light bBucket",
                    47: "Front Right Wheel",
                    48: "Front Left Wheel",
                    49: "Unknown Invisible",
                    50: "Unknown Invisible",
                    51: "Front Right Tire",
                    52: "Front Left Tire",
                    53: "Unknown Invisible",
                    54: "Unknown Invisible",
                    55: "Rear Right Wheel",
                    56: "Rear Left Wheel"}
    
    return geoPartNames[partIdx]


def clearScene(context): # OK
	#for obj in bpy.context.scene.objects:
	#	obj.select_set(True)
	#bpy.ops.object.delete()

	for block in bpy.data.objects:
		#if block.users == 0:
		bpy.data.objects.remove(block, do_unlink = True)

	for block in bpy.data.meshes:
		if block.users == 0:
			bpy.data.meshes.remove(block)

	for block in bpy.data.materials:
		if block.users == 0:
			bpy.data.materials.remove(block)

	for block in bpy.data.textures:
		if block.users == 0:
			bpy.data.textures.remove(block)

	for block in bpy.data.images:
		if block.users == 0:
			bpy.data.images.remove(block)
	
	for block in bpy.data.cameras:
		if block.users == 0:
			bpy.data.cameras.remove(block)
	
	for block in bpy.data.lights:
		if block.users == 0:
			bpy.data.lights.remove(block)
	
	for block in bpy.data.armatures:
		if block.users == 0:
			bpy.data.armatures.remove(block)
	
	for block in bpy.data.collections:
		if block.users == 0:
			bpy.data.collections.remove(block)
		else:
			bpy.data.collections.remove(block, do_unlink=True)


class ImportNFSHSPS1(Operator, ImportHelper):
	"""Load a Need for Speed High Stakes (1999) PS1 model file"""
	bl_idname = "import_nfshsps1.data"  # important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Import models"
	bl_options = {'PRESET'}
	
	# ImportHelper mixin class uses this
	filename_ext = ".geo"
	
	filter_glob: StringProperty(
			options={'HIDDEN'},
			default="*.geo",
			maxlen=255,  # Max internal buffer length, longer would be clamped.
			)
	
	files: CollectionProperty(
			type=OperatorFileListElement,
			)
	
	directory: StringProperty(
			# subtype='DIR_PATH' is not needed to specify the selection mode.
			subtype='DIR_PATH',
			)
	
	# List of operator properties, the attributes will be assigned
	# to the class instance from the operator settings before calling.
	
	is_traffic: BoolProperty(
			name="Is traffic",
			description="Check if the importing vehicle is a traffic",
			default=False,
			)
	
	clear_scene: BoolProperty(
			name="Clear scene",
			description="Check in order to clear the scene",
			default=True,
			)
	
	def execute(self, context): # OK		
		if len(self.files) > 1:
			os.system('cls')
		
			files_path = []
			for file_elem in self.files:
				files_path.append(os.path.join(self.directory, file_elem.name))
			
			print("Importing %d files" % len(files_path))
			
			for file_path in files_path:
				status = main(context, file_path, self.is_traffic, self.clear_scene)
				
				if status == {"CANCELLED"}:
					self.report({"ERROR"}, "Importing of file %s has been cancelled. Check the system console for information." % os.path.splitext(os.path.basename(file_path))[0])
				
				print()
				
			return {'FINISHED'}
		elif os.path.isfile(self.filepath) == False:
			os.system('cls')
			
			files_path = []
			for file in os.listdir(self.filepath):
				file_path = os.path.join(self.filepath, file)
				if os.path.isfile(file_path) == True:
					files_path.append(file_path)
				print("Importing %d files" % len(files_path))
			
			for file_path in files_path:
				status = main(context, file_path, self.is_traffic, self.clear_scene)
				
				if status == {"CANCELLED"}:
					self.report({"ERROR"}, "Importing of file %s has been cancelled. Check the system console for information." % os.path.splitext(os.path.basename(file_path))[0])
				
				print()
				
			return {'FINISHED'}
		else:
			os.system('cls')
			
			status = main(context, self.filepath, self.is_traffic, self.clear_scene)
			
			if status == {"CANCELLED"}:
				self.report({"ERROR"}, "Importing has been cancelled. Check the system console for information.")
			
			return status
	
	def draw(self, context):
		layout = self.layout
		layout.use_property_split = True
		layout.use_property_decorate = False  # No animation.
		
		sfile = context.space_data
		operator = sfile.active_operator
		
		##
		box = layout.box()
		split = box.split(factor=0.75)
		col = split.column(align=True)
		col.label(text="Settings", icon="SETTINGS")
		
		box.prop(operator, "is_traffic")
		
		##
		box = layout.box()
		split = box.split(factor=0.75)
		col = split.column(align=True)
		col.label(text="Preferences", icon="OPTIONS")
		
		box.prop(operator, "clear_scene")


def menu_func_import(self, context):
	pcoll = preview_collections["main"]
	my_icon = pcoll["my_icon"]
	self.layout.operator(ImportNFSHSPS1.bl_idname, text="Need for Speed High Stakes 1999 PS1 (.geo)", icon_value=my_icon.icon_id)


classes = (
		ImportNFSHSPS1,
)

preview_collections = {}

def register():
	import bpy.utils.previews
	pcoll = bpy.utils.previews.new()
	
	my_icons_dir = os.path.join(os.path.dirname(__file__), "polly_icons")
	pcoll.load("my_icon", os.path.join(my_icons_dir, "nfshs_icon.png"), 'IMAGE')

	preview_collections["main"] = pcoll
	
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
	for pcoll in preview_collections.values():
		bpy.utils.previews.remove(pcoll)
	preview_collections.clear()
	
	for cls in classes:
		bpy.utils.unregister_class(cls)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
	register()

