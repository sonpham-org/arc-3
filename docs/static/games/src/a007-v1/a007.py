"""a007 Phantom Load -- infer a hidden beam attachment through controlled load coupling."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,PLATFORM,BEAM,WEIGHT,SAG,SOCKET,GOAL,BAD=6,10,8,14,11,12,5,13,15
LEVELS=[{"name":"Known Weight","seq":(1,3)},{"name":"Moved Socket","seq":(2,3)},{"name":"Coupled Sag","seq":(1,2,3)},{"name":"Link Rotation","seq":(4,2,1,3)},{"name":"Attachment Map","seq":(2,3,1,4,2,1,3)},{"name":"Phantom Load","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 socket,linkage,hidden,evidence,load,detached=s
 if a==1:socket=(socket-1)%6;load=min(4,load+1)
 elif a==2:socket=(socket+2)%6;load=max(1,load-1)
 elif a==3:sag=tuple((load+max(0,4-abs(i-socket))+max(0,3-abs(i-hidden))+linkage*(i%2))%7 for i in range(6));evidence=evidence+((socket,load,linkage,sag),)
 elif a==4:linkage^=1;socket=(socket+3)%6
 elif a==5:detached=(hidden,socket,linkage,load,evidence[-4:])
 return socket,linkage,hidden,evidence,load,detached
for x in LEVELS:
 s=(0,0,4,(),1,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;sag=g.evidence[-1][3] if g.evidence else (0,)*6
  for i,v in enumerate(sag):x=8+(i%3)*18;y=9+(i//3)*16;f[y:y+10,x:x+13]=PLATFORM;f[y+8-v:y+10,x+2:x+11]=SAG;f[y:y+2,x:x+13]=BEAM;f[y+3:y+7,x+4:x+9]=SOCKET if i==g.socket else PLATFORM
  for i,_ in enumerate(g.evidence[-4:]):f[42:48,8+i*12:17+i*12]=WEIGHT
  f[51:55,8:8+g.linkage*22+12]=BEAM
  if g.detached:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A007(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a007",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.socket=self.linkage=0;self.hidden=4;self.evidence=();self.load=1;self.detached=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.socket,self.linkage,self.hidden,self.evidence,self.load,self.detached=advance((self.socket,self.linkage,self.hidden,self.evidence,self.load,self.detached),a)
  elif a==6:
   if (self.socket,self.linkage,self.hidden,self.evidence,self.load,self.detached)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
