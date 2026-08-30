"""q376 Crossing Rig -- construct ferry hardware through alternating controller evidence."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,BANK,FERRY,PART,ASSEMBLY,CONTROL,MARK,BAD=9,10,12,0,15,14,11,6,8
LEVELS=[{"name":"First Ramp","plan":(1,5,4)},{"name":"Joined Dock","plan":(2,1,5,4)},{"name":"Support Mark","plan":(3,2,5,4,1)},{"name":"Dual Controller","plan":(1,5,2,3,5,4)},{"name":"Disjoint Build","plan":(2,1,5,3,4,5,2)},{"name":"Crossing Rig","plan":(3,1,5,2,4,5,3,1)}]
def advance(s,a):
 parts,assembly,controller,marks,route=s;parts=list(parts);marks=list(marks)
 if a in (1,2,3):parts[a-1]+=1;marks[controller]=(marks[controller]+a+parts[a-1])%8
 elif a==4:
  if not sum(parts):return None
  assembly+=1;route=(route+parts[0]*2+parts[1]*3+parts[2]+sum(marks))%5;parts=[max(0,v-1) for v in parts]
 elif a==5:controller=1-controller
 return tuple(parts),assembly,controller,tuple(marks),route
def target(x):
 s=((0,0,0),0,0,(0,0),0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[9:55,3:61]=RIVER;f[5:11,:]=BANK;f[53:60,:]=BANK;f[27:38,21:44]=FERRY
  for i,n in enumerate(g.parts):x=8+i*17;f[13:16,x:x+12]=PART-i;f[17:17+n*5,x:x+12]=PART-i
  for i,v in enumerate(g.marks):f[42+i*4:45+i*4,8:8+v*6]=MARK
  f[56:59,8:8+g.controller*22]=CONTROL;f[48:51,8:8+g.assembly*8]=ASSEMBLY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q376(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.parts=(0,0,0);self.assembly=self.controller=self.route=0;self.marks=(0,0);self.bad=False;self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q376",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.parts=(0,0,0);self.assembly=self.controller=self.route=0;self.marks=(0,0);self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.assembly,self.controller,self.marks,self.route),a)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.assembly,self.controller,self.marks,self.route=s
  elif a==6:
   if (self.parts,self.assembly,self.controller,self.marks,self.route)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
