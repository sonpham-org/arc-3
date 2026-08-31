"""a011 Fuse Surgeon -- contain a spreading overload while preserving powered service."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CIRCUIT,NODE,LINK,OVERLOAD,CUT,BRIDGE,GOAL,BAD=0,10,14,8,12,6,11,13,15
LEVELS=[{"name":"First Cut","seq":(1,)},{"name":"Second Cut","seq":(2,1)},{"name":"Alternate Bridge","seq":(3,1,2)},{"name":"Spread Step","seq":(4,2,1,3)},{"name":"Preserved District","seq":(2,3,1,4,2,1)},{"name":"Fuse Surgeon","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 overload,cuts,bridge,powered,history,sealed=s;c=set(cuts)
 if a==1:c.add((overload+1)%6);powered=max(1,powered-1)
 elif a==2:c.add((overload+3)%6);powered=max(1,powered-1)
 elif a==3:bridge=(overload+2)%6;powered=min(5,powered+2)
 elif a==4:overload=(overload+1+int(overload in c))%6;powered=max(0,powered-int(overload not in c and bridge!=overload));history=history+((overload,tuple(sorted(c)),bridge,powered),)
 elif a==5:sealed=(overload,tuple(sorted(c)),bridge,powered,history[-4:])
 return overload,tuple(sorted(c)),bridge,powered,history,sealed
for x in LEVELS:
 s=(0,(),-1,4,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CIRCUIT;pts=[(10,10),(30,8),(49,12),(15,31),(44,31),(10,49),(51,49)]
  f[15:18,16:49]=LINK;f[33:36,18:45]=LINK;f[20:48,12:15]=LINK;f[20:48,52:55]=LINK
  for i,(x,y) in enumerate(pts):f[y:y+7,x:x+7]=OVERLOAD if i==g.overload else CUT if i in g.cuts else NODE
  if g.bridge>=0:f[26:30,19:48]=BRIDGE
  f[54:58,8:8+g.powered*9]=BRIDGE
  if g.sealed:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A011(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a011",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.overload=0;self.cuts=();self.bridge=-1;self.powered=4;self.history=();self.sealed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.overload,self.cuts,self.bridge,self.powered,self.history,self.sealed=advance((self.overload,self.cuts,self.bridge,self.powered,self.history,self.sealed),a)
  elif a==6:
   if (self.overload,self.cuts,self.bridge,self.powered,self.history,self.sealed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
