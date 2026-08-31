"""a013 Cannibal Workshop -- sacrifice one device to redistribute compatible functions."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,DEVICE,MODULE,SOCKET,DONOR,INVENTORY,GOAL,BAD=2,10,14,8,11,6,12,13,15
LEVELS=[{"name":"Missing Function","seq":(1,)},{"name":"Choose Donor","seq":(2,1)},{"name":"Dismantle","seq":(3,1,2)},{"name":"Compatible Socket","seq":(4,2,1,3)},{"name":"Required Subset","seq":(2,3,1,4,2,1)},{"name":"Cannibal Workshop","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 devices,donor,inventory,target,history,working=s;d=list(devices);inv=list(inventory)
 if a==1:target=(target+1)%4
 elif a==2:donor=(donor+1)%4
 elif a==3:inv[donor%3]+=d[donor]%3+1;d[donor]=0;history=history+(("take",donor,tuple(inv)),)
 elif a==4:
  slot=(target+donor)%3
  if inv[slot]>0:inv[slot]-=1;d[target]|=1<<slot
  history=history+(("fit",target,slot,tuple(d)),)
 elif a==5:working=(tuple(d),donor,tuple(inv),target,history[-5:])
 return tuple(d),donor,tuple(inv),target,history,working
for x in LEVELS:
 s=((3,5,6,1),0,(0,0,0),1,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP
  for i,mask in enumerate(g.devices):x=7+i*14;f[8:30,x:x+11]=DONOR if i==g.donor else DEVICE
  for i,mask in enumerate(g.devices):
   x=8+i*14
   for j in range(3):f[20-j*5:24-j*5,x:x+8]=MODULE if mask&(1<<j) else SOCKET
  for i,v in enumerate(g.inventory):x=9+i*17;f[37:43,x:x+12]=INVENTORY;f[44:47,x:x+2+v*3]=MODULE
  if g.working:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A013(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a013",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.devices=(3,5,6,1);self.donor=0;self.inventory=(0,0,0);self.target=1;self.history=();self.working=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.devices,self.donor,self.inventory,self.target,self.history,self.working=advance((self.devices,self.donor,self.inventory,self.target,self.history,self.working),a)
  elif a==6:
   if (self.devices,self.donor,self.inventory,self.target,self.history,self.working)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
