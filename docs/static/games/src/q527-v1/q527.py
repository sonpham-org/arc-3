"""q527 Spectrum Frame -- compose packet motion through moving prism reference frames."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GALLERY,PRISM,PACKET,LOCAL,SPLIT,LOCK,GOAL,BAD=0,8,11,14,6,10,12,13,15
LEVELS=[
 {"name":"Local Ray","seq":(1,)},{"name":"Turning Pane","seq":(2,1)},
 {"name":"Split Frame","seq":(1,3,2,1)},{"name":"Translated Prism","seq":(2,4,1,3,1)},
 {"name":"Packet Algebra","seq":(1,2,3,4,2,1,3)},
 {"name":"Spectrum Frame","seq":(2,1,4,3,2,1,3,4,1,2,3)}]
def advance(s,a):
 packet,pane,rotation,split,locked=s
 if a==1:packet=(packet+(1 if rotation%2==0 else 2)+pane)%6
 elif a==2:rotation=(rotation+1)%4;pane=(pane+rotation)%4
 elif a==3:split=(split+packet+2*pane+rotation)%6
 elif a==4:pane=(pane+1+split)%4;packet=(packet+pane)%6
 elif a==5:locked=(packet,pane,rotation,split)
 return packet,pane,rotation,split,locked
for x in LEVELS:
 s=(0,0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for i in range(4):
   x=8+i*13;f[9:30,x:x+9]=PRISM if i==g.pane else LOCAL
   f[13+((i+g.rotation)%3)*5:17+((i+g.rotation)%3)*5,x+2:x+7]=SPLIT
  for i in range(6):f[35:41,8+i*8:14+i*8]=PACKET if i==g.packet else LOCAL
  f[46:50,8:8+g.split*8+5]=SPLIT;f[53:57,8:8+g.rotation*11+7]=LOCK
  if g.locked:f[53:58,48:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q527(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q527",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.packet=self.pane=self.rotation=self.split=0;self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.packet,self.pane,self.rotation,self.split,self.locked=advance((self.packet,self.pane,self.rotation,self.split,self.locked),a)
  elif a==6:
   if (self.packet,self.pane,self.rotation,self.split,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
